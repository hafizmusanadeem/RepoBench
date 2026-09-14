"""Loads RepoBench task definitions (benchmark/tasks/task_*.yaml) into
inspect_ai Samples.

Each task YAML describes a real bug in a real repository at a pinned commit.
This module is responsible for:

  1. Strictly validating each task file (bad data fails loudly, at load
     time, rather than silently producing a broken or trivially-passable
     sample).
  2. Building the prompt shown to the agent -- title/description only. The
     base_commit, the fail_to_pass/pass_to_pass test IDs, and the hidden
     test_patch are all kept out of the prompt; they live in Sample.metadata
     where only the harness (setup script + scorer) can see them.
  3. Wiring each Sample to the right per-repository Docker sandbox and a
     setup script that checks out base_commit and runs the task's install
     command.

See benchmark/tasks/TEMPLATE.yaml for how to add a new task.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import yaml
from pydantic import BaseModel, Field, ValidationError

from inspect_ai.dataset import Sample

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASKS_DIR = PROJECT_ROOT / "benchmark" / "tasks"

# Maps a task's `repository` field to the sandbox directory that holds its
# Dockerfile + compose.yaml (see sandbox/<name>/). To evaluate a new
# repository: clone it (full history, not shallow) into repos/<name>, add a
# sandbox/<name>/{Dockerfile,compose.yaml} pair, and register it here.
REPOSITORIES: dict[str, str] = {
    "pydantic-ai": "sandbox/pydantic-ai",
}


class SetupSpec(BaseModel):
    command: str
    env: dict[str, str] = Field(default_factory=dict)


class TestsSpec(BaseModel):
    fail_to_pass: list[str]
    pass_to_pass: list[str] = Field(default_factory=list)


class TaskSpec(BaseModel):
    id: str
    repository: str
    base_commit: str
    title: str
    description: str
    category: str
    difficulty: str
    setup: SetupSpec
    tests: TestsSpec
    timeout_seconds: int = 900
    test_patch: str | None = None
    """Path (relative to this task's yaml file) to a unified diff that adds
    the fail_to_pass regression test(s) on top of base_commit. This is
    applied by the scorer only, after the agent submits -- it is never
    copied into the sandbox or shown to the agent during the episode."""


def _load_task_spec(path: Path) -> TaskSpec:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(
            f"{path}: expected a YAML mapping at the top level, got "
            f"{type(raw).__name__}. (A leading '-' before every key turns "
            "the file into a list of one-key mappings, not a mapping -- "
            "check for stray '-' prefixes at the start of each line.)"
        )
    try:
        return TaskSpec.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"{path}: invalid task definition:\n{e}") from e


def _build_prompt(t: TaskSpec) -> str:
    # Built from separately-dedented pieces rather than one big dedent():
    # dedent() looks at the *shared* leading whitespace across every line of
    # the final string, and the interpolated multi-line description is
    # flush-left, so mixing it into one template silently defeats dedent()
    # for the surrounding lines.
    header = dedent(f"""\
        # {t.title}

        Category: {t.category} | Difficulty: {t.difficulty}
    """).rstrip()
    footer = dedent(f"""\
        You are working inside a checkout of the `{t.repository}` repository
        at /repo. Explore the codebase, implement the smallest correct fix,
        and verify it by running the relevant existing tests. Follow the
        rules in your system prompt -- in particular, do not edit test files
        and do not try to discover or reconstruct the tests that will be
        used to grade you.
    """).rstrip()
    return f"{header}\n\n{t.description.strip()}\n\n{footer}\n"


def _sandbox_for(repository: str) -> tuple[str, str]:
    if repository not in REPOSITORIES:
        raise ValueError(
            f"Unknown repository {repository!r}. Add it to REPOSITORIES in "
            f"{__file__} and provide sandbox/<repository>/{{Dockerfile,compose.yaml}}."
        )
    compose_path = PROJECT_ROOT / REPOSITORIES[repository] / "compose.yaml"
    if not compose_path.is_file():
        raise ValueError(f"Missing sandbox config for {repository!r}: {compose_path}")
    return ("docker", str(compose_path))


def _setup_script(t: TaskSpec) -> str:
    env_exports = "\n".join(f'export {k}="{v}"' for k, v in t.setup.env.items())
    header = dedent(f"""\
        #!/bin/bash
        set -euo pipefail
        cd /repo
        git checkout -f {t.base_commit}
    """).rstrip()
    return f"{header}\n{env_exports}\n{t.setup.command.strip()}\n"


def _read_test_patch(t: TaskSpec, task_file: Path) -> str | None:
    if t.test_patch is None:
        return None
    patch_path = (task_file.parent / t.test_patch).resolve()
    if not patch_path.is_file():
        raise ValueError(f"{task_file}: test_patch {t.test_patch!r} not found at {patch_path}")
    return patch_path.read_text()


def load_dataset(tasks_dir: str | Path = DEFAULT_TASKS_DIR) -> list[Sample]:
    """Load every benchmark/tasks/task_*.yaml file into a list of Samples."""
    tasks_dir = Path(tasks_dir)
    task_files = sorted(tasks_dir.glob("task_*.yaml"))
    if not task_files:
        raise ValueError(f"No task_*.yaml files found in {tasks_dir}")

    samples: list[Sample] = []
    for task_file in task_files:
        t = _load_task_spec(task_file)
        test_patch = _read_test_patch(t, task_file)
        samples.append(
            Sample(
                id=t.id,
                input=_build_prompt(t),
                target=t.id,
                metadata={
                    "repository": t.repository,
                    "base_commit": t.base_commit,
                    "category": t.category,
                    "difficulty": t.difficulty,
                    "fail_to_pass": t.tests.fail_to_pass,
                    "pass_to_pass": t.tests.pass_to_pass,
                    "timeout_seconds": t.timeout_seconds,
                    "test_patch": test_patch,
                },
                sandbox=_sandbox_for(t.repository),
                setup=_setup_script(t),
            )
        )
    return samples
