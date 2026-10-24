"""Fire-and-forget helper. asyncio only keeps a weak reference to a bare
create_task() result, so we hold a strong one until the task finishes."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

_TASKS: set[asyncio.Task[Any]] = set()


def spawn(coro: Coroutine[Any, Any, Any]) -> None:
    task = asyncio.create_task(coro)
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
