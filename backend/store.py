"""A minimal run registry backed by a single JSON file.

There's no database in this project yet, and run history doesn't need one
to get the frontend wired up: this just needs to survive a backend restart
and support "append a run" / "update a run" / "list runs". Records are
stored in the same camelCase shape the API returns (see backend/schemas.py)
so reads don't need any translation.

Swap this for a real database later without touching callers -- they only
use list_runs / get_run / create_run / update_run.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .config import RUNS_STORE_PATH

_lock = threading.Lock()


def _read_all() -> list[dict[str, Any]]:
    if not RUNS_STORE_PATH.exists():
        return []
    try:
        with RUNS_STORE_PATH.open("r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _write_all(records: list[dict[str, Any]]) -> None:
    tmp = RUNS_STORE_PATH.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(records, f, indent=2)
    tmp.replace(RUNS_STORE_PATH)


def list_runs() -> list[dict[str, Any]]:
    with _lock:
        return _read_all()


def get_run(run_id: str) -> dict[str, Any] | None:
    with _lock:
        for record in _read_all():
            if record.get("id") == run_id:
                return record
    return None


def create_run(record: dict[str, Any]) -> None:
    with _lock:
        records = _read_all()
        records.append(record)
        _write_all(records)


def update_run(run_id: str, **updates: Any) -> None:
    with _lock:
        records = _read_all()
        for record in records:
            if record.get("id") == run_id:
                record.update(updates)
                break
        else:
            return
        _write_all(records)
