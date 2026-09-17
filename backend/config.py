from __future__ import annotations

import os
from pathlib import Path

# Importing `backend` (which always happens before this submodule loads)
# already inserts the project root onto sys.path -- see backend/__init__.py.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "backend" / "data"
EVAL_LOG_DIR = DATA_DIR / "logs"
RUNS_STORE_PATH = DATA_DIR / "runs.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
EVAL_LOG_DIR.mkdir(parents=True, exist_ok=True)

# The models offered in the "Agent" dropdown. There is only one agent
# scaffold (agents/coding_agent.py's ReAct loop) -- what actually varies
# between "agents" in the UI is which model drives it, so this is a list of
# inspect_ai model strings (provider/model), e.g. "anthropic/claude-sonnet-4-6".
# Override with a comma-separated REPOBENCH_MODELS env var.
_DEFAULT_MODELS = ["anthropic/claude-sonnet-4-6"]


def available_models() -> list[str]:
    raw = os.environ.get("REPOBENCH_MODELS")
    if not raw:
        return list(_DEFAULT_MODELS)
    models = [m.strip() for m in raw.split(",") if m.strip()]
    return models or list(_DEFAULT_MODELS)


def cors_origins() -> list[str]:
    # The Vite dev server's default origin. Override (comma-separated) with
    # REPOBENCH_CORS_ORIGINS once the frontend is deployed somewhere else.
    raw = os.environ.get("REPOBENCH_CORS_ORIGINS", "http://localhost:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]
