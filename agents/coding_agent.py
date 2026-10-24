"""The RepoBench coding agents.

repo_coding_agent: your original ReAct loop (unchanged) -- now the BASELINE.
build_agent(kind): returns that baseline, or a real coding-agent CLI running in
the sandbox via the `inspect_swe` package (pip install inspect-swe). CLI agents
get their model from eval(model=...) in backend/worker.py, so no model argument
is passed here. Check inspect_swe's docs for options (e.g. attempts, system
prompt) supported by the version you install.
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
    """ReAct agent that fixes a described bug in a sandboxed repo checkout.
    attempts stays 1 so the agent never sees hidden-test feedback."""
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


def build_agent(kind: str, attempts: int = 1, command_timeout: int = 300) -> Agent:
    if kind == "react":
        return repo_coding_agent(attempts=attempts, command_timeout=command_timeout)
    try:
        import inspect_swe
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(f"Agent kind {kind!r} needs `pip install inspect-swe`.") from exc
    factories = {
        "claude_code": "claude_code",
        "codex": "codex_cli",
        "gemini": "gemini_cli",
    }
    if kind not in factories:
        raise ValueError(f"Unknown agent kind {kind!r}")
    return getattr(inspect_swe, factories[kind])()
