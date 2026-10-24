"""The agents you can pick in the UI.

An agent is (kind, model):
  react        your own ReAct scaffold (agents/coding_agent.py) -- the baseline
  claude_code  Claude Code CLI   } via the `inspect_swe` package
  codex        Codex CLI         } (pip install inspect-swe; verify it supports
  gemini       Gemini CLI        }  your inspect_ai version)

Configure with env vars:
  REPOBENCH_MODELS      comma list of models for the react baseline
                        (default anthropic/claude-sonnet-4-6)
  REPOBENCH_CLI_AGENTS  comma list of kind:model, e.g.
                        claude_code:anthropic/claude-sonnet-4-6,codex:openai/gpt-5-codex,gemini:google/gemini-2.5-pro
"""

from __future__ import annotations

import importlib.util
import os
import shutil
from dataclasses import dataclass, field

KINDS = ("react", "claude_code", "codex", "gemini")
_LABELS = {"react": "ReAct baseline", "claude_code": "Claude Code", "codex": "Codex CLI", "gemini": "Gemini CLI"}
_FACTORIES = {"claude_code": "claude_code", "codex": "codex_cli", "gemini": "gemini_cli"}
_CLI_BINARIES = {"claude_code": "claude", "codex": "codex", "gemini": "gemini"}
# Credential env vars that unlock each CLI kind. Only presence is checked —
# values are never read, logged, or passed to the sandbox.
_CLI_CREDENTIALS = {
    "claude_code": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"),
    "codex": ("OPENAI_API_KEY",),
    "gemini": ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY"),
}


@dataclass(frozen=True)
class AgentSpec:
    id: str
    label: str
    kind: str
    model: str
    available: bool = True
    reason: str | None = None


def _check_cli(kind: str) -> tuple[bool, str | None]:
    """Probe whether a CLI agent can run. Read-only: never imports agent
    code beyond a find_spec check, never spawns processes, never makes
    network or model calls."""
    if importlib.util.find_spec("inspect_swe") is None:
        return False, "needs `pip install inspect-swe` (cli-agents extra)"
    try:
        if not hasattr(__import__("inspect_swe", fromlist=["x"]), _FACTORIES[kind]):
            return False, f"installed inspect_swe has no {_FACTORIES[kind]!r} agent"
    except ImportError:
        return False, "needs `pip install inspect-swe` (cli-agents extra)"
    if shutil.which(_CLI_BINARIES[kind]) is None:
        return False, f"CLI binary {_CLI_BINARIES[kind]!r} not found on PATH"
    if not any(os.environ.get(v) for v in _CLI_CREDENTIALS[kind]):
        return False, f"no credential found ({' or '.join(_CLI_CREDENTIALS[kind])})"
    return True, None


def _spec(kind: str, model: str) -> AgentSpec:
    if kind == "react":
        if not model:
            return AgentSpec(id=f"{kind}:", label=_LABELS[kind], kind=kind, model=model,
                             available=False, reason="empty model string")
        return AgentSpec(id=f"{kind}:{model}", label=f"{_LABELS[kind]} · {model}", kind=kind, model=model)
    ok, reason = _check_cli(kind)
    return AgentSpec(id=f"{kind}:{model}", label=f"{_LABELS[kind]} · {model}",
                     kind=kind, model=model, available=ok, reason=reason)


def available_agents() -> list[AgentSpec]:
    specs: list[AgentSpec] = []
    models = os.environ.get("REPOBENCH_MODELS") or "anthropic/claude-sonnet-4-6"
    for m in (x.strip() for x in models.split(",")):
        if m:
            specs.append(_spec("react", m))
    for item in (os.environ.get("REPOBENCH_CLI_AGENTS") or "").split(","):
        item = item.strip()
        if not item:
            continue
        kind, _, model = item.partition(":")
        if kind not in KINDS or not model:
            raise ValueError(f"Bad REPOBENCH_CLI_AGENTS entry {item!r}; expected kind:model with kind in {KINDS}")
        specs.append(_spec(kind, model))
    return specs


def get_agent_spec(agent_id: str) -> AgentSpec:
    for s in available_agents():
        if s.id == agent_id:
            return s
    raise KeyError(f"Unknown agent {agent_id!r}")
