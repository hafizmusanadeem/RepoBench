"""Runs the repo's tests (and the user's verify command) on the CLEAN checkout
before the agent starts, so the scorer can tell pre-existing failures from
regressions the agent caused. User-defined tasks only."""

from __future__ import annotations

from inspect_ai.solver import Generate, TaskState, solver

from .sandbox_utils import run_cmd


@solver
def baseline_solver():
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        meta = state.metadata
        if meta.get("mode") != "user":
            return state
        timeout = int(meta.get("timeout_seconds", 900))
        baseline: dict = {}
        if meta.get("test_command"):
            baseline["tests"] = (await run_cmd(meta["test_command"], timeout)).as_dict()
        if meta.get("verify_command"):
            baseline["verify"] = (await run_cmd(meta["verify_command"], timeout)).as_dict()
        state.metadata["baseline"] = baseline
        return state

    return solve
