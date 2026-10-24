"""Orchestrates an Evaluation: build the repo image once, then run every
(agent x epoch) as its own worker subprocess, a few at a time.

Evaluation -> Runs. Epochs are separate runs (not inspect's `epochs=`) so each
repeat is visible, comparable and live-updating in the UI.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timezone

from . import store
from .bg import spawn
from .config import MAX_PARALLEL_RUNS, PROJECT_ROOT, RUN_TIME_LIMIT
from .sandbox import build_image, write_sandbox
from .schemas import EvaluationCreate

_SEM = asyncio.Semaphore(MAX_PARALLEL_RUNS)

# In-memory pid map so cancel endpoints can signal a live worker. A server
# restart loses the handle; such runs are reconciled by fail_orphans().
_WORKER_PIDS: dict[str, int] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_name(url: str) -> str:
    return url.rstrip("/").split("/")[-1].removesuffix(".git") or "repo"


async def start_evaluation(p: EvaluationCreate, repo: dict | None, bench_title: str | None) -> str:
    ev_id = str(uuid.uuid4())
    if repo is not None:
        task_label = f"{_repo_name(repo['url'])}:{p.kind}"
        title = p.title.strip() or f"{p.kind.replace('_', ' ').title()} in {_repo_name(repo['url'])}"
        test_command = p.test_command if p.test_command is not None else repo["profile"]["testCommand"]
    else:
        task_label = p.benchmark_task_id or "benchmark"
        title = p.title.strip() or bench_title or task_label
        test_command = ""
    ev = {
        "id": ev_id, "repoId": repo["id"] if repo else None, "repoUrl": repo["url"] if repo else None,
        "repoCommit": repo["commit"] if repo else None,
        "benchmarkTaskId": p.benchmark_task_id, "kind": p.kind, "title": title,
        "description": p.description, "errorLog": p.error_log, "verifyCommand": p.verify_command,
        "testCommand": test_command, "agents": p.agents, "epochs": p.epochs,
        "maxToolCalls": p.max_tool_calls, "judge": p.judge,
        "status": "building" if repo else "running", "errorMessage": None,
    }
    store.create("evaluations", ev, parent=ev["repoId"])
    for agent in p.agents:
        for epoch in range(1, p.epochs + 1):
            store.create("runs", {
                "id": str(uuid.uuid4()), "evaluationId": ev_id, "taskId": task_label, "taskTitle": title,
                "agent": agent, "epoch": epoch, "status": "queued", "result": None,
                "createdAt": _now(), "completedAt": None, "errorMessage": None, "transcript": [],
            }, parent=ev_id)
    spawn(_run_evaluation(ev_id))
    return ev_id


async def _run_evaluation(ev_id: str) -> None:
    ev = store.get("evaluations", ev_id)
    assert ev is not None
    runs = store.list_("runs", parent=ev_id)
    try:
        if ev["repoId"]:
            repo = store.get("repos", ev["repoId"])
            assert repo is not None
            compose = write_sandbox(repo)  # pick up any profile edits
            ok, tail = await build_image(compose)
            if not ok:
                raise RuntimeError(f"Docker image build failed:\n{tail}")
            store.update("evaluations", ev_id, status="running")
        await asyncio.gather(*(_run_worker(r["id"]) for r in runs))
        store.update("evaluations", ev_id, status="complete", completedAt=_now())
    except Exception as exc:  # noqa: BLE001
        for r in runs:
            current = store.get("runs", r["id"])
            if current and current["status"] in ("queued", "running"):
                store.update("runs", r["id"], status="error", errorMessage=str(exc)[-1500:], completedAt=_now())
        store.update("evaluations", ev_id, status="error", errorMessage=str(exc)[-1500:])


async def _run_worker(run_id: str) -> None:
    async with _SEM:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "backend.worker", run_id, cwd=str(PROJECT_ROOT),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        _WORKER_PIDS[run_id] = proc.pid or 0
        try:
            # RUN_TIME_LIMIT bounds inspect_ai, not the process itself; the
            # grace period covers scoring + artifact writes after the limit.
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=RUN_TIME_LIMIT + 300)
        except asyncio.TimeoutError:
            proc.kill()
            out, _ = await proc.communicate()
            store.update("runs", run_id, status="error", completedAt=_now(),
                         errorMessage=f"Worker timed out after {RUN_TIME_LIMIT + 300}s and was killed.")
            return
        finally:
            _WORKER_PIDS.pop(run_id, None)
    run = store.get("runs", run_id)
    if run and run["status"] in ("queued", "running"):  # worker died without reporting
        tail = out.decode(errors="replace")[-1500:]
        store.update("runs", run_id, status="error", completedAt=_now(),
                     errorMessage=f"Worker exited with code {proc.returncode}.\n{tail}")


def cancel_run(run_id: str) -> bool:
    """Signal a live worker; mark the run error. Returns False if no live worker."""
    pid = _WORKER_PIDS.get(run_id)
    run = store.get("runs", run_id)
    if run is None or run.get("status") not in ("queued", "running"):
        return False
    if pid:
        try:
            import os
            os.kill(pid, 9)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    _WORKER_PIDS.pop(run_id, None)
    store.update("runs", run_id, status="error", completedAt=_now(),
                 errorMessage="Cancelled by the user.")
    return True
