"""Build an inspect_ai Sample from a user-defined evaluation (feature / bug
report / failing test / refactor) against a cloned repo."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from inspect_ai.dataset import Sample

from .config import SANDBOX_DIR

RULES = (Path(__file__).resolve().parent.parent / "agents" / "system_prompt.txt").read_text()

_INTRO = {
    "feature": "Implement the following feature.",
    "bug": "Find and fix the bug described below.",
    "failing_test": "Make the failing test or command described below pass by fixing the production code, not the test.",
    "refactor": "Perform the following refactor without changing behaviour.",
}


def build_prompt(ev: dict[str, Any], include_rules: bool) -> str:
    parts = [f"# {ev['title']}", _INTRO[ev["kind"]], ev["description"].strip()]
    if ev.get("errorLog", "").strip():
        parts.append("## Error output\n```\n" + ev["errorLog"].strip() + "\n```")
    checks = []
    if ev.get("verifyCommand"):
        checks.append(f"- This command must succeed when you are done: `{ev['verifyCommand']}`")
    if ev.get("testCommand"):
        checks.append(f"- Tests run with `{ev['testCommand']}`; tests that passed before must still pass.")
    if checks:
        parts.append("## How your work is checked\n" + "\n".join(checks))
    parts.append("You are working inside a checkout of the repository at /repo. Make the smallest correct change and verify it by running the relevant tests.")
    if include_rules:  # CLI agents don't get agents/system_prompt.txt, so inline it
        parts.append("## Rules\n" + RULES)
    return "\n\n".join(p for p in parts if p)


def build_sample(repo: dict[str, Any], ev: dict[str, Any], run_id: str, include_rules: bool) -> Sample:
    compose = SANDBOX_DIR / repo["id"] / "compose.yaml"
    setup = f"#!/bin/bash\nset -euo pipefail\ncd /repo\ngit checkout -f {shlex.quote(repo['commit'])}\n"
    return Sample(
        id=run_id,
        input=build_prompt(ev, include_rules),
        target=run_id,
        metadata={
            "mode": "user",
            "kind": ev["kind"],
            "description": ev["description"],
            "test_command": ev.get("testCommand", ""),
            "verify_command": ev.get("verifyCommand", ""),
            "protect_tests": ev["kind"] in ("bug", "failing_test"),
            "judge": bool(ev.get("judge")),
            "timeout_seconds": 900,
        },
        sandbox=("docker", str(compose)),
        setup=setup,
    )
