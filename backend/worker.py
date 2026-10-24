"""Executes ONE run in its own process:  python -m backend.worker <run_id>

Running each eval in a subprocess (instead of inside uvicorn's event loop, as
the old runner did) means an API --reload or crash no longer kills in-flight
runs, and runs can't block each other. Results go to the SQLite store.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone

from inspect_ai import eval_async

from agents.coding_agent import build_agent
from benchmark.dataset import load_dataset
from evals.repobench import repobench_task

from . import store
from .agents_registry import get_agent_spec
from .config import EVAL_LOG_DIR, RUN_TIME_LIMIT
from .taskbuilder import RULES, build_sample
from .transcript import build_transcript, extract_metrics, sample_result, total_duration


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sample_for(ev: dict, run_id: str, include_rules: bool):
    if ev.get("benchmarkTaskId"):
        sample = next(s for s in load_dataset() if s.id == ev["benchmarkTaskId"])
        if include_rules:
            sample = sample.model_copy(update={"input": f"{sample.input}\n\n## Rules\n{RULES}"})
        return sample
    repo = store.get("repos", ev["repoId"])
    assert repo is not None
    return build_sample(repo, ev, run_id, include_rules)


async def _run(run_id: str) -> None:
    run = store.get("runs", run_id)
    assert run is not None
    ev = store.get("evaluations", run["evaluationId"])
    assert ev is not None
    try:
        spec = get_agent_spec(run["agent"])
        store.update("runs", run_id, status="running")
        sample = _sample_for(ev, run_id, include_rules=spec.kind != "react")
        task = repobench_task(
            [sample],
            agent=build_agent(spec.kind),
            message_limit=ev["maxToolCalls"],
            time_limit=RUN_TIME_LIMIT,
        )
        logs = await eval_async(task, model=spec.model, log_dir=str(EVAL_LOG_DIR), display="none")
        log = logs[0] if logs else None
        if log is None or log.status == "error" or not log.samples:
            msg = log.error.message if log is not None and log.error is not None else "The evaluation produced no result."
            store.update("runs", run_id, status="error", errorMessage=msg, completedAt=_now())
            return
        sample_log = log.samples[0]
        if sample_log.error is not None:
            store.update("runs", run_id, status="error", errorMessage=sample_log.error.message, completedAt=_now())
            return
        transcript = build_transcript(sample_log)
        metrics = extract_metrics(sample_log, transcript)
        baseline = sample_log.metadata.get("baseline") or {}
        metrics["baselineTestsOk"] = baseline.get("tests", {}).get("success")
        metrics["baselineVerifyOk"] = baseline.get("verify", {}).get("success")
        store.update(
            "runs", run_id, status="success", result=sample_result(sample_log),
            duration=total_duration(sample_log), completedAt=_now(), transcript=transcript, **metrics,
        )
    except Exception as exc:  # noqa: BLE001
        store.update("runs", run_id, status="error", errorMessage=f"{type(exc).__name__}: {exc}", completedAt=_now())


if __name__ == "__main__":
    asyncio.run(_run(sys.argv[1]))
