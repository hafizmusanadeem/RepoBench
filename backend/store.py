"""SQLite document store (stdlib only, no new dependency).

Replaces the old runs.json. Every table is (id, parent, created_at, data) where
`data` is the camelCase JSON record the API returns, so reads need no
translation. WAL mode + a busy timeout make it safe for the API process and the
per-run worker subprocesses (backend/worker.py) to write at the same time.

Tables: repos, evaluations (parent = repo id), runs (parent = evaluation id),
votes (parent = evaluation id).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from .config import DB_PATH

TABLES = ("repos", "evaluations", "runs", "votes")
# Heavy fields left out of list responses.
_HEAVY = ("transcript", "patch")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        yield conn
    finally:
        conn.close()


SCHEMA_VERSION = 1


def _init() -> None:
    with _conn() as c:
        for t in TABLES:
            c.execute(
                f"CREATE TABLE IF NOT EXISTS {t} ("
                "id TEXT PRIMARY KEY, parent TEXT, created_at TEXT, data TEXT NOT NULL)"
            )
            c.execute(f"CREATE INDEX IF NOT EXISTS idx_{t}_parent ON {t}(parent)")
        c.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)")
        row = c.execute("SELECT version FROM schema_version").fetchone()
        if row is None:
            c.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        # Future migrations: if row[0] < SCHEMA_VERSION, migrate step by step.
        # All current records are schemaless JSON documents, so additive field
        # changes need no migration; a version bump here only matters when a
        # structural change lands.


_init()


def create(table: str, record: dict[str, Any], parent: str | None = None) -> None:
    record.setdefault("createdAt", _now())
    with _conn() as c:
        c.execute(
            f"INSERT INTO {table} (id, parent, created_at, data) VALUES (?,?,?,?)",
            (record["id"], parent, record["createdAt"], json.dumps(record)),
        )


def get(table: str, record_id: str) -> dict[str, Any] | None:
    with _conn() as c:
        row = c.execute(f"SELECT data FROM {table} WHERE id=?", (record_id,)).fetchone()
    return json.loads(row[0]) if row else None


def update(table: str, record_id: str, **updates: Any) -> None:
    with _conn() as c:
        c.execute("BEGIN IMMEDIATE")
        try:
            row = c.execute(f"SELECT data FROM {table} WHERE id=?", (record_id,)).fetchone()
            if row is None:
                c.execute("ROLLBACK")
                return
            record = json.loads(row[0])
            record.update(updates)
            c.execute(f"UPDATE {table} SET data=? WHERE id=?", (json.dumps(record), record_id))
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise


def list_(table: str, parent: str | None = None, light: bool = True,
          limit: int | None = None) -> list[dict[str, Any]]:
    """Newest first, optionally bounded. `light` strips transcript/patch."""
    clause = f" LIMIT {max(1, min(limit, 10_000))}" if limit is not None else ""
    with _conn() as c:
        if parent is None:
            rows = c.execute(f"SELECT data FROM {table} ORDER BY created_at DESC{clause}").fetchall()
        else:
            rows = c.execute(
                f"SELECT data FROM {table} WHERE parent=? ORDER BY created_at DESC{clause}", (parent,)
            ).fetchall()
    records = [json.loads(r[0]) for r in rows]
    if light:
        for r in records:
            for key in _HEAVY:
                r.pop(key, None)
    return records


def fail_orphans() -> None:
    """Called on API startup: anything still in flight belongs to a server
    process that no longer exists."""
    msg = "The API server restarted while this was in progress."
    for r in list_("runs", light=True):
        if r.get("status") in ("queued", "running"):
            update("runs", r["id"], status="error", errorMessage=msg, completedAt=_now())
    for e in list_("evaluations"):
        if e.get("status") in ("building", "running"):
            update("evaluations", e["id"], status="error", errorMessage=msg)
    for repo in list_("repos"):
        if repo.get("status") == "cloning":
            update("repos", repo["id"], status="error", errorMessage=msg)
