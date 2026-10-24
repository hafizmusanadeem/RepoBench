"""RepoBench: repository-specific coding-agent evaluation.

    inspect eval evals/repobench.py --model anthropic/claude-sonnet-4-6

`repobench` is the original CLI task over benchmark/tasks/*.yaml.
`repobench_task` builds a one-sample Task from any Sample list + agent; the
backend worker (backend/worker.py) uses it for user-defined evaluations.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.agent import Agent, as_solver  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.solver import chain  # noqa: E402

from agents.coding_agent import repo_coding_agent  # noqa: E402
from benchmark.baseline import baseline_solver  # noqa: E402
from benchmark.dataset import load_dataset  # noqa: E402
from benchmark.scorer import repo_test_scorer  # noqa: E402


def repobench_task(
    samples: list[Sample], agent: Agent, message_limit: int = 120, time_limit: int | None = None
) -> Task:
    return Task(
        dataset=samples,
        solver=chain(baseline_solver(), as_solver(agent)),
        scorer=repo_test_scorer(),
        message_limit=message_limit,
        time_limit=time_limit,
    )


@task
def repobench(
    tasks_dir: str = str(_PROJECT_ROOT / "benchmark" / "tasks"),
    attempts: int = 1,
    command_timeout: int = 300,
    message_limit: int = 120,
) -> Task:
    """Evaluate the ReAct baseline against RepoBench's bug-fix tasks."""
    return repobench_task(
        load_dataset(tasks_dir),
        repo_coding_agent(attempts=attempts, command_timeout=command_timeout),
        message_limit=message_limit,
    )
