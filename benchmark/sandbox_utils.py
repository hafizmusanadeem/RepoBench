"""Small helpers shared by the baseline solver and the scorer."""

from __future__ import annotations

import re
from dataclasses import dataclass

from inspect_ai.util import sandbox

_KEEP = 60_000


@dataclass
class CmdResult:
    success: bool
    exit_code: int
    output: str

    def as_dict(self) -> dict:
        return {"success": self.success, "exit_code": self.exit_code, "output": self.output}


async def run_cmd(cmd: str, timeout: int) -> CmdResult:
    try:
        r = await sandbox().exec(["bash", "-lc", cmd], cwd="/repo", timeout=timeout)
    except TimeoutError:
        return CmdResult(False, 124, f"[timed out after {timeout}s]")
    return CmdResult(r.success, r.returncode, (r.stdout + r.stderr)[-_KEEP:])


# One line per failing test, across the common runners (pytest -rf, go test,
# cargo test, jest/vitest). Heuristic: it lets us tell "this test was already
# failing before the agent touched anything" from "the agent broke it".
_FAIL_RES = [
    re.compile(r"^FAILED\s+(\S+)", re.M),
    re.compile(r"^--- FAIL:\s+(\S+)", re.M),
    re.compile(r"^test (\S+) \.\.\. FAILED", re.M),
    re.compile(r"^\s*(?:FAIL|✕|×)\s+(.+?)\s*$", re.M),
]


def failing_set(output: str) -> set[str]:
    found: set[str] = set()
    for rx in _FAIL_RES:
        found.update(m.strip() for m in rx.findall(output))
    return found
