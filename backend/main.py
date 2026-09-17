"""RepoBench API.

Run with (from the project root):

    uv run uvicorn backend.main:app --reload --port 8000

See backend/README.md for details, including how this connects to the
Vite dev server.
"""

from __future__ import annotations

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from benchmark.dataset import DEFAULT_TASKS_DIR, TaskSpec

from . import runner, store
from .config import available_models, cors_origins
from .schemas import CreateRunRequest, DashboardMetrics, RunDetail, RunSummary, TaskSummary

app = FastAPI(title="RepoBench API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_tasks() -> list[TaskSummary]:
    tasks: list[TaskSummary] = []
    for path in sorted(DEFAULT_TASKS_DIR.glob("task_*.yaml")):
        spec = TaskSpec.model_validate(yaml.safe_load(path.read_text()))
        tasks.append(
            TaskSummary(
                id=spec.id,
                title=spec.title,
                category=spec.category,
                difficulty=spec.difficulty,
                repository=spec.repository,
            )
        )
    return tasks


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/tasks", response_model=list[TaskSummary])
def get_tasks() -> list[TaskSummary]:
    return _load_tasks()


@app.get("/api/agents", response_model=list[str])
def get_agents() -> list[str]:
    return available_models()


@app.get("/api/runs", response_model=list[RunSummary])
def get_runs() -> list[RunSummary]:
    records = sorted(store.list_runs(), key=lambda r: r["createdAt"], reverse=True)
    return [RunSummary.model_validate(record) for record in records]


@app.get("/api/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str) -> RunDetail:
    record = store.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunDetail.model_validate(record)


@app.post("/api/runs", response_model=RunSummary, status_code=201)
async def create_run(payload: CreateRunRequest) -> RunSummary:
    tasks_by_id = {t.id: t for t in _load_tasks()}
    task = tasks_by_id.get(payload.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Unknown task {payload.task_id!r}")

    run_id = await runner.start_run(
        task_id=task.id,
        task_title=task.title,
        agent=payload.agent,
        max_tool_calls=payload.max_tool_calls,
    )
    record = store.get_run(run_id)
    assert record is not None  # just created it above
    return RunSummary.model_validate(record)


@app.get("/api/dashboard/metrics", response_model=DashboardMetrics)
def get_dashboard_metrics() -> DashboardMetrics:
    records = store.list_runs()
    passed = sum(1 for r in records if r.get("result") == "PASS")
    failed = sum(1 for r in records if r.get("result") == "FAIL")
    running = sum(1 for r in records if r.get("status") == "running")
    total = passed + failed
    success_rate = round((passed / total) * 100, 1) if total else 0.0
    return DashboardMetrics(
        total=total,
        passed=passed,
        failed=failed,
        running=running,
        success_rate=success_rate,
    )
