"""Launches a real evals.repobench.repobench evaluation for a single task
and tracks it in backend/store.py.

This calls inspect_ai exactly the way the project's own CLI usage does
(`inspect eval evals/repobench.py --model ...`), just through eval_async()
instead of the CLI, filtered to one sample via `sample_id`, and run as a
background asyncio task so POST /api/runs can return immediately.

Requires the same things running evals from the CLI already requires:
Docker (for the per-repository sandbox), the repo checked out under
repos/<name> (see repos/README.md), and credentials for whichever model is
selected. If any of that isn't available, the run finishes with
status="error" and errorMessage explaining why -- it does not crash the
server.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from inspect_ai import eval_async

from evals.repobench import repobench

from . import store
from .config import EVAL_LOG_DIR
from .transcript import build_transcript, sample_result, total_duration


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def start_run(task_id: str, task_title: str, agent: str, max_tool_calls: int) -> str:
    """Creates a "running" run record and kicks off the real evaluation in
    the background. Returns the new run's id immediately."""
    run_id = str(uuid.uuid4())
    record = {
        "id": run_id,
        "taskId": task_id,
        "taskTitle": task_title,
        "agent": agent,
        "status": "running",
        "result": None,
        "toolCallCount": None,
        "duration": None,
        "createdAt": _now(),
        "completedAt": None,
        "errorMessage": None,
        "transcript": [],
    }
    store.create_run(record)

    # Fire-and-forget: the event loop this coroutine runs in is uvicorn's,
    # which stays alive for the life of the server, so this keeps running
    # after the POST /api/runs request that started it has returned.
    task = asyncio.create_task(_execute(run_id, task_id, agent, max_tool_calls))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    return run_id


# Keep a reference to in-flight background tasks -- asyncio only holds a
# weak reference to a bare create_task() result, so without this the task
# can be garbage-collected mid-run.
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()


async def _execute(run_id: str, task_id: str, agent: str, max_tool_calls: int) -> None:
    try:
        task = repobench(message_limit=max_tool_calls)
        logs = await eval_async(
            task,
            model=agent,
            sample_id=task_id,
            log_dir=str(EVAL_LOG_DIR),
        )
        log = logs[0] if logs else None

        if log is None or log.status == "error" or not log.samples:
            error_message = (
                log.error.message
                if log is not None and log.error is not None
                else "The evaluation produced no result -- check the backend logs."
            )
            store.update_run(
                run_id,
                status="error",
                errorMessage=error_message,
                completedAt=_now(),
            )
            return

        sample = log.samples[0]
        transcript = build_transcript(sample)
        store.update_run(
            run_id,
            status="success",
            result=sample_result(sample),
            toolCallCount=len(transcript),
            duration=total_duration(sample),
            completedAt=_now(),
            transcript=transcript,
        )
    except Exception as exc:  # noqa: BLE001 - surface any failure to the UI instead of losing it
        store.update_run(
            run_id,
            status="error",
            errorMessage=f"{type(exc).__name__}: {exc}",
            completedAt=_now(),
        )
