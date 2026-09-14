"""Scorer for RepoBench tasks.

Grading happens entirely inside the sample's own Docker sandbox, after the
agent has submitted:

  1. Look at what files the agent actually changed (`git diff --name-only`).
     If it touched any file that the hidden test patch also touches, that's
     a scoring violation (rule: don't edit the tests) and we fail fast
     without even applying the patch.
  2. Apply the task's hidden test patch (the regression test(s) that don't
     exist at base_commit). If it fails to apply, the agent's changes are
     incompatible with the real fix shape -- also a failure, reported
     distinctly from a normal test failure.
  3. Run fail_to_pass, then pass_to_pass, inside the sandbox.
  4. Score CORRECT only if every fail_to_pass and every pass_to_pass test
     passes.

None of this ever sends the hidden test content back to the agent -- the
episode has already ended by the time this runs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target, accuracy, scorer, stderr
from inspect_ai.solver import TaskState
from inspect_ai.util import sandbox

_OUTPUT_TAIL_CHARS = 4000


@dataclass
class _TestRun:
    success: bool
    output: str


def _patch_touched_paths(patch: str) -> set[str]:
    """Extract the 'b/...' file paths a unified diff touches."""
    return set(re.findall(r"^\+\+\+ b/(\S+)", patch, flags=re.MULTILINE))


async def _run_pytest(node_ids: list[str], timeout: int) -> _TestRun:
    if not node_ids:
        return _TestRun(success=True, output="(no tests specified)")
    result = await sandbox().exec(
        ["python3", "-m", "pytest", "-q", *node_ids],
        cwd="/repo",
        timeout=timeout,
    )
    return _TestRun(success=result.success, output=(result.stdout + result.stderr))


@scorer(metrics=[accuracy(), stderr()])
def repo_test_scorer():
    async def score(state: TaskState, target: Target) -> Score:
        meta = state.metadata
        fail_to_pass: list[str] = meta["fail_to_pass"]
        pass_to_pass: list[str] = meta.get("pass_to_pass", [])
        test_patch: str | None = meta.get("test_patch")
        timeout = int(meta.get("timeout_seconds", 900))

        explanation: list[str] = []

        if test_patch:
            protected_paths = _patch_touched_paths(test_patch)
            diff = await sandbox().exec(["git", "diff", "--name-only"], cwd="/repo")
            touched_paths = set(diff.stdout.split())
            collisions = touched_paths & protected_paths
            if collisions:
                return Score(
                    value=INCORRECT,
                    explanation=(
                        "Scoring violation: the agent modified test file(s) "
                        f"{sorted(collisions)} that the grading patch also needs to "
                        "touch. Fixes must not edit test files -- see system prompt "
                        "rule 3."
                    ),
                )

            await sandbox().write_file("/tmp/repobench_test_patch.diff", test_patch)
            applied = await sandbox().exec(
                ["git", "apply", "/tmp/repobench_test_patch.diff"], cwd="/repo"
            )
            if not applied.success:
                return Score(
                    value=INCORRECT,
                    explanation=(
                        "Could not apply the grading test patch on top of the "
                        "agent's changes. This usually means the fix altered code "
                        "the real regression test depends on in an incompatible "
                        f"way:\n{applied.stderr}"
                    ),
                )
            explanation.append("Applied the hidden regression test patch successfully.")

        f2p = await _run_pytest(fail_to_pass, timeout)
        explanation.append(
            f"fail_to_pass [{'PASSED' if f2p.success else 'FAILED'}] {fail_to_pass}\n"
            f"{f2p.output[-_OUTPUT_TAIL_CHARS:]}"
        )

        p2p = await _run_pytest(pass_to_pass, timeout)
        explanation.append(
            f"pass_to_pass [{'PASSED' if p2p.success else 'FAILED'}] {pass_to_pass}\n"
            f"{p2p.output[-_OUTPUT_TAIL_CHARS:]}"
        )

        correct = f2p.success and p2p.success
        return Score(
            value=CORRECT if correct else INCORRECT,
            explanation="\n\n".join(explanation),
        )

    return score
