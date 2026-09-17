"""Turns an inspect_ai EvalSample (the in-memory result of one evaluated
task) into the plain JSON shapes backend/schemas.py declares.

The agent's tools are bash, text_editor, and think (see
agents/coding_agent.py) plus the react() agent's own submit tool -- real
tool names, not the "edit_file" / "run_command" / "read_file" placeholders
the frontend mock data used. frontend/src/pages/RunDetails.tsx renders
these real names/argument shapes directly.
"""

from __future__ import annotations

from typing import Any

from inspect_ai._util.content import (
    ContentAudio,
    ContentDocument,
    ContentImage,
    ContentText,
    ContentVideo,
)
from inspect_ai.event._tool import ToolEvent
from inspect_ai.log import EvalSample


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    seconds = max(0.0, seconds)
    minutes, secs = divmod(int(round(seconds)), 60)
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _stringify_result(result: Any) -> str | None:
    if result is None:
        return None
    if isinstance(result, str):
        return result
    if isinstance(result, (int, float, bool)):
        return str(result)
    if isinstance(result, (ContentText, ContentDocument)):
        return result.text
    if isinstance(result, (ContentImage, ContentAudio, ContentVideo)):
        return f"[{type(result).__name__.removeprefix('Content').lower()} content]"
    if isinstance(result, list):
        parts = [_stringify_result(item) for item in result]
        return "\n".join(p for p in parts if p)
    return str(result)


def build_transcript(sample: EvalSample) -> list[dict[str, Any]]:
    """One ToolCall dict (see schemas.ToolCall) per tool the agent invoked,
    in the order they happened."""
    calls: list[dict[str, Any]] = []
    step = 0
    for event in sample.events:
        if not isinstance(event, ToolEvent):
            continue
        step += 1
        failed = bool(event.failed) or event.error is not None
        calls.append(
            {
                "id": event.id or event.uuid or f"{sample.id}-{step}",
                "step": step,
                "tool": event.function,
                "status": "Failed" if failed else "Success",
                "duration": _format_duration(event.working_time),
                "arguments": event.arguments,
                "output": None if failed else _stringify_result(event.result),
                "error": event.error.message if event.error else None,
            }
        )
    return calls


def total_duration(sample: EvalSample) -> str:
    return _format_duration(sample.total_time)


def sample_result(sample: EvalSample) -> str | None:
    """PASS/FAIL from the repo_test_scorer score, or None if the sample
    wasn't scored (e.g. the episode errored before completing)."""
    if not sample.scores:
        return None
    score = sample.scores.get("repo_test_scorer") or next(iter(sample.scores.values()), None)
    if score is None:
        return None
    return "PASS" if str(score.value) == "C" else "FAIL"
