"""RepoBench API.  uv run uvicorn backend.main:app --reload --port 8000
See backend/README.md."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from benchmark.dataset import DEFAULT_TASKS_DIR, TaskSpec

from . import repos, runner, store
from .agents_registry import available_agents
from .config import cors_origins
from .recommend import build_recommendation
from .schemas import (
    AgentBreakdown, AgentInfo, DashboardMetrics, EvaluationCreate, EvaluationDetail, EvaluationSummary,
    Profile, Recommendation, RepoCreate, RepoOut, RunDetail, RunSummary, TaskSummary, VoteCreate,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.fail_orphans()
    yield


app = FastAPI(title="RepoBench API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=cors_origins(), allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


def _load_tasks() -> list[TaskSummary]:
    out = []
    for path in sorted(DEFAULT_TASKS_DIR.glob("task_*.yaml")):
        s = TaskSpec.model_validate(yaml.safe_load(path.read_text()))
        out.append(TaskSummary(id=s.id, title=s.title, category=s.category, difficulty=s.difficulty, repository=s.repository))
    return out


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/tasks", response_model=list[TaskSummary])
def get_tasks() -> list[TaskSummary]:
    return _load_tasks()


@app.get("/api/agents", response_model=list[str])
def get_agents() -> list[str]:
    return [a.id for a in available_agents()]


@app.get("/api/agents/info", response_model=list[AgentInfo])
def get_agents_info() -> list[AgentInfo]:
    return [AgentInfo(id=a.id, label=a.label, kind=a.kind, model=a.model,
                      available=a.available, reason=a.reason) for a in available_agents()]


# ---- repos -----------------------------------------------------------------

@app.post("/api/repos", response_model=RepoOut, status_code=201)
def post_repo(payload: RepoCreate) -> RepoOut:
    try:
        return RepoOut.model_validate(repos.register_repo(payload.url, payload.ref))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/api/repos", response_model=list[RepoOut])
def get_repos() -> list[RepoOut]:
    return [RepoOut.model_validate(r) for r in store.list_("repos")]


@app.get("/api/repos/{repo_id}", response_model=RepoOut)
def get_repo(repo_id: str) -> RepoOut:
    r = store.get("repos", repo_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    return RepoOut.model_validate(r)


@app.put("/api/repos/{repo_id}/profile", response_model=RepoOut)
def put_profile(repo_id: str, profile: Profile) -> RepoOut:
    try:
        return RepoOut.model_validate(repos.set_profile(repo_id, profile))
    except KeyError:
        raise HTTPException(status_code=409, detail="Repo isn't ready yet")


# ---- evaluations -----------------------------------------------------------

def _summary(ev: dict, runs: list[dict]) -> dict:
    return {**ev, "runCount": len(runs), "doneCount": sum(1 for r in runs if r["status"] in ("success", "error"))}


@app.post("/api/evaluations", response_model=EvaluationSummary, status_code=201)
async def post_evaluation(p: EvaluationCreate) -> EvaluationSummary:
    known = {a.id for a in available_agents()}
    bad = [a for a in p.agents if a not in known]
    if bad:
        raise HTTPException(status_code=422, detail=f"Unknown agent(s): {bad}")
    unavailable = {a.id: a.reason for a in available_agents() if not a.available}
    blocked = [a for a in p.agents if a in unavailable]
    if blocked:
        detail = "; ".join(f"{a} ({unavailable[a]})" for a in blocked)
        raise HTTPException(status_code=422, detail=f"Agent(s) not available: {detail}")
    repo, bench_title = None, None
    if p.repo_id:
        repo = store.get("repos", p.repo_id)
        if repo is None or repo["status"] != "ready":
            raise HTTPException(status_code=409, detail="Repo isn't ready yet")
        if not p.description.strip():
            raise HTTPException(status_code=422, detail="Describe the task.")
        profile = repo.get("profile") or {}
        effective_test_command = (
            p.test_command if p.test_command is not None else profile.get("testCommand", "")
        )
        has_command_check = bool(p.verify_command.strip() or (effective_test_command or "").strip())
        if p.kind in ("bug", "failing_test") and not p.verify_command.strip():
            raise HTTPException(
                status_code=422,
                detail="Bug tasks need a specific verify command that fails before the fix and passes afterward. The repository test command only checks for regressions; an error log alone cannot verify a fix.",
            )
        if p.kind in ("feature", "refactor") and not (has_command_check or p.judge):
            raise HTTPException(
                status_code=422,
                detail="Provide a verify command, a repository test command, or enable the model review so the result can be evaluated.",
            )
    elif p.benchmark_task_id:
        match = next((t for t in _load_tasks() if t.id == p.benchmark_task_id), None)
        if match is None:
            raise HTTPException(status_code=404, detail=f"Unknown task {p.benchmark_task_id!r}")
        bench_title = match.title
    else:
        raise HTTPException(status_code=422, detail="Provide repoId or benchmarkTaskId.")
    ev_id = await runner.start_evaluation(p, repo, bench_title)
    ev = store.get("evaluations", ev_id)
    assert ev is not None
    return EvaluationSummary.model_validate(_summary(ev, store.list_("runs", parent=ev_id)))


@app.get("/api/evaluations", response_model=list[EvaluationSummary])
def get_evaluations(limit: int = Query(200, ge=1, le=1000)) -> list[EvaluationSummary]:
    return [EvaluationSummary.model_validate(_summary(e, store.list_("runs", parent=e["id"]))) for e in store.list_("evaluations", limit=limit)]


@app.get("/api/evaluations/{ev_id}", response_model=EvaluationDetail)
def get_evaluation(ev_id: str) -> EvaluationDetail:
    ev = store.get("evaluations", ev_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    runs = sorted(store.list_("runs", parent=ev_id), key=lambda r: (r["agent"], r.get("epoch") or 0))
    return EvaluationDetail.model_validate({**_summary(ev, runs), "runs": runs})


@app.get("/api/evaluations/{ev_id}/recommendation", response_model=Recommendation)
def get_recommendation(
    ev_id: str,
    w_success: float = Query(70, ge=0), w_cost: float = Query(15, ge=0), w_time: float = Query(15, ge=0),
) -> Recommendation:
    if store.get("evaluations", ev_id) is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    rec = build_recommendation(
        store.list_("runs", parent=ev_id), store.list_("votes", parent=ev_id),
        {"success": w_success, "cost": w_cost, "time": w_time},
    )
    return Recommendation.model_validate(rec)


@app.post("/api/evaluations/{ev_id}/votes", status_code=201)
def post_vote(ev_id: str, v: VoteCreate) -> dict[str, str]:
    if store.get("evaluations", ev_id) is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    if v.run_a == v.run_b:
        raise HTTPException(status_code=422, detail="Choose two different runs to compare.")
    run_ids = {r["id"] for r in store.list_("runs", parent=ev_id)}
    if v.run_a not in run_ids or v.run_b not in run_ids:
        raise HTTPException(status_code=422, detail="Both runs must belong to this evaluation.")
    vid = str(uuid.uuid4())
    store.create("votes", {"id": vid, "runA": v.run_a, "runB": v.run_b, "winner": v.winner}, parent=ev_id)
    return {"id": vid}


# ---- runs ------------------------------------------------------------------

@app.get("/api/runs", response_model=list[RunSummary])
def get_runs(evaluation_id: str | None = None) -> list[RunSummary]:
    return [RunSummary.model_validate(r) for r in store.list_("runs", parent=evaluation_id)]


@app.get("/api/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str) -> RunDetail:
    record = store.get("runs", run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunDetail.model_validate(record)


@app.delete("/api/runs/{run_id}", response_model=dict[str, bool])
def cancel_run(run_id: str) -> dict[str, bool]:
    """Signal a live worker and mark the run error. Safe to call on a
    finished run (returns cancelled=false)."""
    if store.get("runs", run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"cancelled": runner.cancel_run(run_id)}


@app.delete("/api/evaluations/{ev_id}", response_model=dict[str, int])
def cancel_evaluation(ev_id: str) -> dict[str, int]:
    """Cancel every unfinished run in the evaluation."""
    if store.get("evaluations", ev_id) is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    n = 0
    for r in store.list_("runs", parent=ev_id):
        if r.get("status") in ("queued", "running") and runner.cancel_run(r["id"]):
            n += 1
        elif r.get("status") in ("queued", "running"):
            store.update("runs", r["id"], status="error", completedAt=None,
                         errorMessage="Cancelled by the user (no live worker; likely orphaned).")
            n += 1
    if n and store.get("evaluations", ev_id).get("status") in ("building", "running"):
        store.update("evaluations", ev_id, status="error", errorMessage="Cancelled by the user.")
    return {"cancelled": n}


# ---- dashboard -------------------------------------------------------------

@app.get("/api/dashboard/metrics", response_model=DashboardMetrics)
def get_dashboard_metrics() -> DashboardMetrics:
    records = store.list_("runs")
    passed = sum(1 for r in records if r.get("result") == "PASS")
    failed = sum(1 for r in records if r.get("result") == "FAIL")
    errored = sum(1 for r in records if r.get("status") == "error")
    running = sum(1 for r in records if r.get("status") in ("running", "queued"))
    graded = passed + failed
    agents = sorted({r["agent"] for r in records})
    by_agent = [
        AgentBreakdown(
            agent=a,
            passed=sum(1 for r in records if r["agent"] == a and r.get("result") == "PASS"),
            failed=sum(1 for r in records if r["agent"] == a and r.get("result") == "FAIL"),
            errored=sum(1 for r in records if r["agent"] == a and r.get("status") == "error"),
        ) for a in agents
    ]
    return DashboardMetrics(
        total=len(records), passed=passed, failed=failed, running=running, errored=errored,
        success_rate=round(passed / graded * 100, 1) if graded else 0.0, by_agent=by_agent,
    )
