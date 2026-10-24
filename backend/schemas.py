from __future__ import annotations

from typing import Any, Literal

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

TaskKind = Literal["feature", "bug", "failing_test", "refactor"]


class ApiModel(BaseModel):
    """Fields are snake_case in Python and camelCase in JSON."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class TaskSummary(ApiModel):
    id: str
    title: str
    category: str
    difficulty: str
    repository: str


class AgentInfo(ApiModel):
    id: str
    label: str
    kind: str
    model: str
    available: bool = True
    reason: str | None = None


class Profile(ApiModel):
    language: str = "unknown"
    package_manager: str = ""
    base_image: str = "ubuntu:24.04"
    install_command: str = ""
    test_command: str = ""
    build_command: str = ""
    lint_command: str = ""
    notes: list[str] = Field(default_factory=list)

    @field_validator("base_image")
    @classmethod
    def _check_base_image(cls, v: str) -> str:
        """Allowlist for the Docker `FROM` line (see backend/sandbox.py).

        The value is interpolated into a generated Dockerfile, so anything
        outside `name[:tag][@digest]` characters - whitespace, newlines,
        shell metacharacters - is rejected instead of written out.
        """
        if not v or len(v) > 256 or not re.fullmatch(r"[A-Za-z0-9._/:@-]+", v):
            raise ValueError(
                "base_image must look like 'ubuntu:24.04' or "
                "'python:3.12-slim' (letters, digits, . _ / : @ - only)."
            )
        return v


class RepoCreate(ApiModel):
    url: str
    ref: str | None = None


class RepoOut(ApiModel):
    id: str
    url: str
    ref: str | None = None
    commit: str | None = None
    status: Literal["cloning", "ready", "error"]
    error_message: str | None = None
    profile: Profile | None = None
    created_at: str


class ToolCall(ApiModel):
    id: str
    step: int
    tool: str
    """Registered tool name ("bash", "text_editor", "think", "submit", ...) or
    "assistant_message" for the model's own text."""
    status: Literal["Success", "Failed"]
    duration: str
    arguments: dict[str, Any]
    output: str | None = None
    error: str | None = None


class RunSummary(ApiModel):
    id: str
    evaluation_id: str | None = None
    task_id: str
    task_title: str
    agent: str
    epoch: int | None = None
    status: Literal["queued", "running", "success", "error"]
    """Whether the run itself finished; see `result` for whether the fix was correct."""
    result: Literal["PASS", "FAIL"] | None = None
    tool_call_count: int | None = None
    failed_tool_calls: int | None = None
    duration: str | None = None
    duration_seconds: float | None = None
    tokens: int | None = None
    cost_usd: float | None = None
    files_changed: int | None = None
    additions: int | None = None
    deletions: int | None = None
    regressions: int | None = None
    baseline_tests_ok: bool | None = None
    baseline_verify_ok: bool | None = None
    created_at: str
    completed_at: str | None = None
    error_message: str | None = None


class RunDetail(RunSummary):
    transcript: list[ToolCall] = Field(default_factory=list)
    patch: str | None = None


class EvaluationCreate(ApiModel):
    repo_id: str | None = None
    benchmark_task_id: str | None = None
    kind: TaskKind = "bug"
    title: str = ""
    description: str = ""
    error_log: str = ""
    verify_command: str = ""
    test_command: str | None = None
    agents: list[str] = Field(min_length=1)
    epochs: int = Field(default=1, ge=1, le=10)
    max_tool_calls: int = Field(default=60, ge=1, le=500)
    judge: bool = False


class EvaluationSummary(ApiModel):
    id: str
    repo_id: str | None = None
    repo_url: str | None = None
    repo_commit: str | None = None
    benchmark_task_id: str | None = None
    kind: str
    title: str
    description: str
    agents: list[str]
    epochs: int
    status: Literal["building", "running", "complete", "error"]
    error_message: str | None = None
    created_at: str
    run_count: int = 0
    done_count: int = 0


class EvaluationDetail(EvaluationSummary):
    verify_command: str = ""
    test_command: str = ""
    error_log: str = ""
    runs: list[RunSummary] = Field(default_factory=list)


class AgentStats(ApiModel):
    agent: str
    n: int
    passes: int
    errors: int
    success_rate: float
    ci_low: float
    ci_high: float
    median_duration_s: float | None = None
    median_cost_usd: float | None = None
    median_tokens: int | None = None
    regression_rate: float
    wins: int = 0
    losses: int = 0
    ties: int = 0
    score: float


class Recommendation(ApiModel):
    best_agent: str | None
    confidence: Literal["none", "low", "medium", "high"]
    summary: str
    stats: list[AgentStats]
    weights: dict[str, float]


class VoteCreate(ApiModel):
    run_a: str
    run_b: str
    winner: Literal["a", "b", "tie"]


class AgentBreakdown(ApiModel):
    agent: str
    passed: int
    failed: int
    errored: int


class DashboardMetrics(ApiModel):
    total: int
    passed: int
    failed: int
    running: int
    errored: int = 0
    success_rate: float
    by_agent: list[AgentBreakdown] = Field(default_factory=list)
