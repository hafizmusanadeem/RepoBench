"""Scorer for RepoBench tasks.

Two modes, chosen by sample metadata["mode"]:

benchmark (hand-written YAML tasks, original behaviour)
  1. fail fast if the agent touched a file the hidden test patch also touches
  2. apply the hidden test patch, run fail_to_pass then pass_to_pass
  3. CORRECT only if everything passes

user (any cloned repo; feature / bug / failing_test / refactor)
  1. (bug kinds) fail if the agent edited or deleted an existing test file
  2. verify_command, if given, must succeed
  3. the repo's test_command must not regress versus the baseline captured
     before the agent started (benchmark/baseline.py); pre-existing failures
     are not blamed on the agent
  4. optional LLM judge (feature tasks) on the diff

Either way the agent's final diff (including new files) is captured FIRST, into
Score.metadata["patch"], for the compare view.
"""

from __future__ import annotations

import os
import re

from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target, accuracy, scorer, stderr
from inspect_ai.solver import TaskState
from inspect_ai.util import sandbox

from .sandbox_utils import CmdResult, failing_set, run_cmd

_TAIL = 4000
_PATCH_CAP = 400_000
_TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|spec)(/|$)|(^|/)(test_[^/]*|[^/]*_test\.\w+|[^/]*\.(test|spec)\.\w+)$"
)


def _patch_touched_paths(patch: str) -> set[str]:
    return set(re.findall(r"^\+\+\+ b/(\S+)", patch, flags=re.MULTILINE))


async def _snapshot_changes() -> tuple[str, list[list[str]]]:
    """Agent's full diff vs HEAD, including untracked files, leaving the index
    as it found it."""
    sb = sandbox()
    await sb.exec(["git", "add", "-A"], cwd="/repo")
    names = await sb.exec(["git", "diff", "--cached", "--name-status", "HEAD"], cwd="/repo")
    diff = await sb.exec(["git", "diff", "--cached", "HEAD"], cwd="/repo")
    await sb.exec(["git", "reset", "-q"], cwd="/repo")
    patch = diff.stdout
    if len(patch) > _PATCH_CAP:
        patch = patch[:_PATCH_CAP] + "\n[patch truncated]\n"
    entries = [ln.split("\t") for ln in names.stdout.splitlines() if ln.strip()]
    return patch, entries


async def _run_pytest(node_ids: list[str], timeout: int) -> CmdResult:
    if not node_ids:
        return CmdResult(True, 0, "(no tests specified)")
    r = await sandbox().exec(["python3", "-m", "pytest", "-q", *node_ids], cwd="/repo", timeout=timeout)
    return CmdResult(r.success, r.returncode, r.stdout + r.stderr)


async def _score_benchmark(state: TaskState) -> Score:
    meta = state.metadata
    fail_to_pass: list[str] = meta["fail_to_pass"]
    pass_to_pass: list[str] = meta.get("pass_to_pass", [])
    test_patch: str | None = meta.get("test_patch")
    timeout = int(meta.get("timeout_seconds", 900))
    patch, entries = await _snapshot_changes()
    info = {"patch": patch}
    explanation: list[str] = []

    if test_patch:
        collisions = {e[-1] for e in entries} & _patch_touched_paths(test_patch)
        if collisions:
            return Score(value=INCORRECT, metadata=info, explanation=(
                f"Scoring violation: the agent modified test file(s) {sorted(collisions)} that the "
                "grading patch also needs to touch (system prompt rule 3)."))
        await sandbox().write_file("/tmp/repobench_test_patch.diff", test_patch)
        applied = await sandbox().exec(["git", "apply", "/tmp/repobench_test_patch.diff"], cwd="/repo")
        if not applied.success:
            return Score(value=INCORRECT, metadata=info, explanation=(
                "Could not apply the grading test patch on top of the agent's changes:\n" + applied.stderr))
        explanation.append("Applied the hidden regression test patch successfully.")

    f2p = await _run_pytest(fail_to_pass, timeout)
    explanation.append(f"fail_to_pass [{'PASSED' if f2p.success else 'FAILED'}] {fail_to_pass}\n{f2p.output[-_TAIL:]}")
    p2p = await _run_pytest(pass_to_pass, timeout)
    explanation.append(f"pass_to_pass [{'PASSED' if p2p.success else 'FAILED'}] {pass_to_pass}\n{p2p.output[-_TAIL:]}")
    ok = f2p.success and p2p.success
    return Score(value=CORRECT if ok else INCORRECT, explanation="\n\n".join(explanation),
                 metadata={**info, "regressions": 0 if p2p.success else 1})


def _compare(base: dict | None, after: CmdResult) -> tuple[bool, int, str]:
    """(ok, regression_count, note) for the repo's own test suite."""
    if after.success:
        return True, 0, "all tests pass"
    after_f = failing_set(after.output)
    if base is None or base["success"]:
        return False, max(len(after_f), 1), "tests passed before the agent started and fail now"
    base_f = failing_set(base["output"])
    if not after_f or not base_f:
        return False, 1, "tests were already failing and the runner output can't be compared; treated as a failure"
    new = after_f - base_f
    return (not new), len(new), (f"{len(new)} new failing test(s)" if new else "only pre-existing failures remain")


async def _judge(description: str, patch: str) -> tuple[bool, str]:
    from inspect_ai.model import get_model

    judge_name = os.environ.get("REPOBENCH_JUDGE_MODEL")
    model = get_model(judge_name) if judge_name else get_model()
    out = await model.generate(
        "You are reviewing a code change.\n\nRequested change:\n" + description +
        "\n\nDiff:\n" + patch[:60_000] +
        "\n\nDoes the diff fully and correctly implement the request without unrelated changes? "
        "Reply with one short paragraph, then a final line exactly `VERDICT: YES` or `VERDICT: NO`."
    )
    text = out.completion
    return "VERDICT: YES" in text.upper(), text[-800:]


async def _score_user(state: TaskState) -> Score:
    meta = state.metadata
    timeout = int(meta.get("timeout_seconds", 900))
    baseline = meta.get("baseline") or {}
    patch, entries = await _snapshot_changes()
    notes: list[str] = []
    info = {"patch": patch, "regressions": 0}

    if meta.get("protect_tests"):
        edited: list[str] = []
        for entry in entries:
            status = entry[0]
            paths = entry[1:]
            # Statuses M/D/R/C can alter or remove an existing test. Rename and
            # copy records contain both old and new paths, so inspect every path.
            if status[:1] in ("M", "D", "R", "C"):
                edited.extend(path for path in paths if _TEST_PATH.search(path))
        edited = sorted(set(edited))
        if edited:
            return Score(value=INCORRECT, metadata=info, explanation=f"The agent edited, removed, renamed, or copied existing test file(s): {edited}")

    verify_ok = True
    if meta.get("verify_command"):
        baseline_verify_passed = bool(baseline.get("verify", {}).get("success"))
        v = await run_cmd(meta["verify_command"], timeout)
        verify_ok = v.success
        notes.append(f"verify `{meta['verify_command']}` [{'PASSED' if v.success else 'FAILED'}]\n{v.output[-_TAIL:]}")
        if meta.get("kind") in ("bug", "failing_test") and baseline_verify_passed:
            verify_ok = False
            notes.append("Verification failed as an evaluation criterion: this bug/failing-test command already passed before the agent started, so it does not demonstrate that the requested issue was fixed.")
        elif baseline_verify_passed:
            notes.append("Warning: the verify command already passed before the agent started, so it does not discriminate between a fix and the baseline.")

    tests_ok = True
    if meta.get("test_command"):
        after = await run_cmd(meta["test_command"], timeout)
        tests_ok, regressions, note = _compare(baseline.get("tests"), after)
        info["regressions"] = regressions
        notes.append(f"tests [{'OK' if tests_ok else 'REGRESSED'}] {note}\n{after.output[-_TAIL:]}")

    judge_ok = True
    if meta.get("judge"):
        judge_ok, verdict = await _judge(meta.get("description", ""), patch)
        notes.append(f"judge [{'YES' if judge_ok else 'NO'}]\n{verdict}")

    correct = verify_ok and tests_ok and judge_ok
    if not patch.strip():
        correct = False
        notes.insert(0, "The agent made no changes.")
    return Score(value=CORRECT if correct else INCORRECT, explanation="\n\n".join(notes), metadata=info)


@scorer(metrics=[accuracy(), stderr()])
def repo_test_scorer():
    async def score(state: TaskState, target: Target) -> Score:
        if state.metadata.get("mode") == "user":
            return await _score_user(state)
        return await _score_benchmark(state)

    return score
