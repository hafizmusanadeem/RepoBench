from __future__ import annotations

import json
import os
from pathlib import Path

# Importing `backend` (which always happens before this submodule loads)
# already inserts the project root onto sys.path -- see backend/__init__.py.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "backend" / "data"
EVAL_LOG_DIR = DATA_DIR / "logs"
SANDBOX_DIR = DATA_DIR / "sandboxes"   # generated Dockerfile + compose.yaml per repo
DB_PATH = DATA_DIR / "repobench.db"
REPOS_DIR = PROJECT_ROOT / "repos"     # cloned repositories (gitignored)

for _d in (DATA_DIR, EVAL_LOG_DIR, SANDBOX_DIR, REPOS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# How many agent runs execute at the same time (each is its own Docker sandbox
# plus its own worker process).
MAX_PARALLEL_RUNS = int(os.environ.get("REPOBENCH_MAX_PARALLEL_RUNS", "2"))

# Wall-clock limit for one agent run, in seconds.
RUN_TIME_LIMIT = int(os.environ.get("REPOBENCH_RUN_TIME_LIMIT", "1800"))

# USD per 1M tokens as (input, output), matched by substring against the model
# string inspect_ai reports. CHECK THESE against your provider's pricing page
# before trusting any cost number; override with REPOBENCH_PRICES, e.g.
#   REPOBENCH_PRICES='{"gpt-5": [1.25, 10.0]}'
_DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    "claude-sonnet-4": (3.0, 15.0),
}


def model_prices() -> dict[str, tuple[float, float]]:
    prices = dict(_DEFAULT_PRICES)
    raw = os.environ.get("REPOBENCH_PRICES")
    if raw:
        for key, value in json.loads(raw).items():
            prices[key] = (float(value[0]), float(value[1]))
    return prices


def cors_origins() -> list[str]:
    raw = os.environ.get("REPOBENCH_CORS_ORIGINS", "http://localhost:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]
