"""RepoBench: repository-specific coding-agent evaluation.

    inspect eval evals/repobench.py --model anthropic/claude-sonnet-4-6

Each sample: checks out a real repository at a pinned commit inside an
isolated, network-disabled Docker sandbox; gives a ReAct coding agent a bug
description; lets it explore/edit/test the repo; then grades the result by
applying a hidden regression-test patch and running it, plus the existing
pass_to_pass tests. See benchmark/dataset.py and benchmark/scorer.py for the
mechanics, and benchmark/tasks/TEMPLATE.yaml for how to add a task.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `python -m inspect_ai eval evals/repobench.py` (or opening this file
# directly) to import the top-level `agents` / `benchmark` packages without
# requiring the project to be pip-installed first.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from inspect_ai import Task, task  # noqa: E402

from agents.coding_agent import repo_coding_agent  # noqa: E402
from benchmark.dataset import load_dataset  # noqa: E402
from benchmark.scorer import repo_test_scorer  # noqa: E402


@task
def repobench(
    tasks_dir: str = str(_PROJECT_ROOT / "benchmark" / "tasks"),
    attempts: int = 1,
    command_timeout: int = 300,
    message_limit: int = 120,
) -> Task:
    """Evaluate a coding agent against RepoBench's bug-fix tasks.

    Args:
        tasks_dir: Directory of task_*.yaml files to load.
        attempts: Graded submission attempts allowed per sample (see
            agents/coding_agent.py for why this defaults to 1).
        command_timeout: Per-tool-call timeout in seconds for bash/text_editor.
        message_limit: Max messages per sample before the episode is cut off.
    """
    return Task(
        dataset=load_dataset(tasks_dir),
        solver=repo_coding_agent(attempts=attempts, command_timeout=command_timeout),
        scorer=repo_test_scorer(),
        message_limit=message_limit,
    )
