"""The RepoBench coding agent: a ReAct loop (reason -> act -> observe ->
repeat) over a real repository checked out in a Docker sandbox.

Built on inspect_ai's react() agent (see
https://inspect.aisi.org.uk/react-agent.html) rather than a hand-rolled
loop, so we get the tool-call loop, submit-tool handling, and message-limit
handling for free. The agent's own iteration -- edit, run pytest, read the
failure, edit again -- happens naturally through repeated bash() calls; no
special-casing is needed for that, it's just what a ReAct agent with a
shell does.

`attempts` is intentionally 1 by default: inspect_ai's react(attempts=N)
re-invokes the task scorer on each submission and tells the model whether
it was correct, which would hand the agent feedback derived from the hidden
regression test across retries. Keeping attempts=1 means the agent only
ever sees test output it generated itself (the existing/pass_to_pass
suite), consistent with system_prompt.txt rule 7.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from inspect_ai.agent import Agent, agent, react
from inspect_ai.tool import bash, text_editor, think

_SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.txt"

_THINK_TOOL_PROMPT = dedent("""\
    Use the think tool to reason before acting: to plan how you'll reproduce
    the bug, to interpret test output before deciding what to change, or to
    weigh between a couple of candidate fixes before you edit anything. It
    does not read or change the repository -- it only logs your reasoning.
""")


def _load_system_prompt() -> str:
    return _SYSTEM_PROMPT_PATH.read_text()


@agent
def repo_coding_agent(attempts: int = 1, command_timeout: int = 300) -> Agent:
    """A ReAct agent that fixes a described bug in a sandboxed repo checkout.

    Args:
        attempts: Number of graded submission attempts. Defaults to 1 -- see
            module docstring for why this matters for this benchmark.
        command_timeout: Per-call timeout (seconds) for bash and text_editor
            tool invocations, so a hung command (e.g. an accidentally
            interactive process) can't stall a sample forever.
    """
    return react(
        name="repo_coding_agent",
        description=(
            "Software engineer that fixes a described bug in a repository "
            "checkout and verifies the fix by running tests."
        ),
        prompt=_load_system_prompt(),
        tools=[
            bash(timeout=command_timeout),
            text_editor(timeout=command_timeout),
            think(_THINK_TOOL_PROMPT),
        ],
        attempts=attempts,
    )
