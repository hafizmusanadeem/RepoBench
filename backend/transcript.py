"""Turns an inspect_ai EvalSample into the JSON shapes backend/schemas.py
declares: transcript, PASS/FAIL, patch, token/cost and diff metrics.

Storage safety: per-event output/error text is capped and secrets are
redacted before anything is written to SQLite; total events are capped too.
"""

from __future__ import annotations

import re
from typing import Any

from inspect_ai._util.content import (
    ContentAudio,
    ContentDocument,
    ContentImage,
    ContentText,
    ContentVideo,
)
from inspect_ai.event._model import ModelEvent
from inspect_ai.event._tool import ToolEvent
from inspect_ai.log import EvalSample

from .config import model_prices

# Per-event text cap + total-event cap: large logs otherwise bloat SQLite.
_EVENT_TEXT_CAP = 20_000
_MAX_EVENTS = 200

# Secrets that must never reach stored logs or API responses. Only the
# well-known prefixes/shapes are matched; values are never read back.
_REDACTIONS = [
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}"), "[REDACTED-anthropic-key]"),
    (re.compile(r"sk-or-v1-[A-Za-z0-9_-]{8,}"), "[REDACTED-openrouter-key]"),
    (re.compile(r"\bsk-[A-Za-z0-9]{8,}"), "[REDACTED-api-key]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED-aws-key]"),
    (re.compile(r"\bxox[bpas]-[A-Za-z0-9-]{8,}"), "[REDACTED-slack-token]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{8,}"), "[REDACTED-github-token]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
     "[REDACTED-private-key]"),
]


def redact(text: str | None) -> str | None:
    """Replace known secret shapes with placeholders."""
    if not text:
        return text
    for rx, placeholder in _REDACTIONS:
        text = rx.sub(placeholder, text)
    return text


def _cap(text: str | None) -> str | None:
    if text is None:
        return None
    text = redact(text)
    assert text is not None
    if len(text) > _EVENT_TEXT_CAP:
        return text[:_EVENT_TEXT_CAP] + f"\n[output truncated at {_EVENT_TEXT_CAP} chars]\n"
    return text


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    seconds = max(0.0, seconds)
    minutes, secs = divmod(int(round(seconds)), 60)
    return f"{minutes}m {secs}s" if minutes else f"{secs}s"


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
        return "\n".join(p for p in (_stringify_result(i) for i in result) if p)
    return str(result)


def build_transcript(sample: EvalSample) -> list[dict[str, Any]]:
    """Tool calls plus the model's own text, in the order they happened."""
    calls: list[dict[str, Any]] = []
    step = 0
    for event in sample.events:
        if isinstance(event, ModelEvent):
            try:
                text = (event.output.completion or "").strip()
            except Exception:  # noqa: BLE001
                text = ""
            if text:
                step += 1
                calls.append({
                    "id": f"{sample.id}-msg-{step}", "step": step, "tool": "assistant_message",
                    "status": "Success", "duration": "—", "arguments": {},
                    "output": _cap(text), "error": None,
                })
            continue
        if not isinstance(event, ToolEvent):
            continue
        step += 1
        failed = bool(event.failed) or event.error is not None
        calls.append({
            "id": event.id or event.uuid or f"{sample.id}-{step}",
            "step": step,
            "tool": event.function,
            "status": "Failed" if failed else "Success",
            "duration": _format_duration(event.working_time),
            "arguments": event.arguments,
            "output": None if failed else _cap(_stringify_result(event.result)),
            "error": _cap(event.error.message) if event.error else None,
        })
    if len(calls) > _MAX_EVENTS:
        # Keep the head (setup/repro) and the tail (final edits/verify).
        keep_head = _MAX_EVENTS // 2
        calls = calls[:keep_head] + [{
            "id": f"{sample.id}-truncated", "step": keep_head + 1, "tool": "assistant_message",
            "status": "Success", "duration": "—", "arguments": {},
            "output": f"[{len(calls) - _MAX_EVENTS} middle events omitted for storage]",
            "error": None,
        }] + calls[-(_MAX_EVENTS - keep_head):]
    return calls


def total_duration(sample: EvalSample) -> str:
    return _format_duration(sample.total_time)


def _score(sample: EvalSample):
    if not sample.scores:
        return None
    return sample.scores.get("repo_test_scorer") or next(iter(sample.scores.values()), None)


def sample_result(sample: EvalSample) -> str | None:
    score = _score(sample)
    if score is None:
        return None
    return "PASS" if str(score.value) == "C" else "FAIL"


def estimate_cost(sample: EvalSample) -> float | None:
    """USD from reported token usage and the price table in config.py. None
    when no model matched a price (so the UI shows "—", not a fake $0)."""
    prices = model_prices()
    total, matched = 0.0, False
    for model, usage in (sample.model_usage or {}).items():
        for key, (p_in, p_out) in prices.items():
            if key in model:
                total += usage.input_tokens * p_in / 1e6 + usage.output_tokens * p_out / 1e6
                matched = True
                break
    return round(total, 4) if matched else None


def extract_metrics(sample: EvalSample, transcript: list[dict[str, Any]]) -> dict[str, Any]:
    score = _score(sample)
    meta = (score.metadata or {}) if score is not None else {}
    patch: str = meta.get("patch") or ""
    additions = sum(1 for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++"))
    deletions = sum(1 for l in patch.splitlines() if l.startswith("-") and not l.startswith("---"))
    tokens = sum(u.total_tokens or (u.input_tokens + u.output_tokens) for u in (sample.model_usage or {}).values())
    real_calls = [t for t in transcript if t["tool"] != "assistant_message"]
    return {
        "patch": patch or None,
        "filesChanged": patch.count("\ndiff --git") + (1 if patch.startswith("diff --git") else 0),
        "additions": additions,
        "deletions": deletions,
        "regressions": int(meta.get("regressions") or 0),
        "tokens": tokens or None,
        "costUsd": estimate_cost(sample),
        "durationSeconds": float(sample.total_time) if sample.total_time is not None else None,
        "toolCallCount": len(real_calls),
        "failedToolCalls": sum(1 for t in real_calls if t["status"] == "Failed"),
    }
