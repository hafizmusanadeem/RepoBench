from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Base for every response/request model: fields are declared
    snake_case in Python but serialize as camelCase JSON, matching the
    frontend's existing conventions (toolCallCount, taskId, ...)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class TaskSummary(ApiModel):
    id: str
    title: str
    category: str
    difficulty: str
    repository: str


class ToolCall(ApiModel):
    id: str
    step: int
    tool: str
    """The tool's registered name, e.g. "bash", "text_editor", "think",
    "submit" -- see agents/coding_agent.py for the tools available to the
    agent."""
    status: Literal["Success", "Failed"]
    duration: str
    arguments: dict[str, Any]
    output: str | None = None
    error: str | None = None


class RunSummary(ApiModel):
    id: str
    task_id: str
    task_title: str
    agent: str
    status: Literal["running", "success", "error"]
    """Run-level status: whether the evaluation itself completed, not
    whether the agent's fix was correct -- see `result` for that."""
    result: Literal["PASS", "FAIL"] | None = None
    tool_call_count: int | None = None
    duration: str | None = None
    created_at: str
    completed_at: str | None = None
    error_message: str | None = None


class RunDetail(RunSummary):
    transcript: list[ToolCall] = Field(default_factory=list)


class DashboardMetrics(ApiModel):
    total: int
    passed: int
    failed: int
    running: int
    success_rate: float


class CreateRunRequest(ApiModel):
    task_id: str
    agent: str
    max_tool_calls: int = 20
