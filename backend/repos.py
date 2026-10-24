"""Register a repository: validate the URL, clone it, profile it, generate its
sandbox files."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
from datetime import datetime, timezone

from . import store
from .bg import spawn
from .config import REPOS_DIR
from .profiler import profile_repo
from .sandbox import write_sandbox
from .schemas import Profile

_URL_RE = re.compile(r"^(https://|ssh://|git@)[^\s]+$")
_REF_RE = re.compile(r"^[\w][\w./-]*$")


def repo_id_for(url: str, ref: str | None) -> str:
    return hashlib.sha1(f"{url}@{ref or ''}".encode()).hexdigest()[:10]


async def _run(*args: str, cwd: str | None = None, timeout: int = 1800) -> str:
    proc = await asyncio.create_subprocess_exec(
        *args, cwd=cwd, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"`{' '.join(args[:3])}` timed out after {timeout}s")
    text = out.decode(errors="replace")
    if proc.returncode:
        raise RuntimeError(text[-2000:])
    return text


def register_repo(url: str, ref: str | None) -> dict:
    url = url.strip()
    ref = (ref or "").strip() or None
    if not _URL_RE.match(url):
        raise ValueError("Use an https://, ssh:// or git@ repository URL.")
    if ref and not _REF_RE.match(ref):
        raise ValueError("Invalid branch, tag or commit.")
    repo_id = repo_id_for(url, ref)
    existing = store.get("repos", repo_id)
    if existing and existing["status"] != "error":
        return existing
    record = {"id": repo_id, "url": url, "ref": ref, "commit": None, "status": "cloning",
              "errorMessage": None, "profile": None}
    if existing:
        store.update("repos", repo_id, **record)
    else:
        store.create("repos", record)
    spawn(_clone_and_profile(repo_id))
    return store.get("repos", repo_id) or record


async def _clone_and_profile(repo_id: str) -> None:
    repo = store.get("repos", repo_id)
    assert repo is not None
    dest = REPOS_DIR / repo_id
    try:
        if dest.exists():
            shutil.rmtree(dest)
        # Full clone, NOT --filter=blob:none: the sandbox has no network, so
        # `git checkout <commit>` inside it can't fetch missing blobs later.
        await _run("git", "clone", "--", repo["url"], str(dest))
        if repo["ref"]:
            await _run("git", "checkout", "--", repo["ref"], cwd=str(dest))
        commit = (await _run("git", "rev-parse", "HEAD", cwd=str(dest))).strip()
        profile = Profile(**profile_repo(dest))
        record = {**repo, "commit": commit, "profile": profile.model_dump(by_alias=True)}
        write_sandbox(record)
        store.update("repos", repo_id, commit=commit, profile=record["profile"], status="ready", errorMessage=None)
    except Exception as exc:  # noqa: BLE001
        store.update("repos", repo_id, status="error", errorMessage=str(exc)[-1500:])


def set_profile(repo_id: str, profile: Profile) -> dict:
    repo = store.get("repos", repo_id)
    if repo is None or repo["status"] != "ready":
        raise KeyError(repo_id)
    data = profile.model_dump(by_alias=True)
    store.update("repos", repo_id, profile=data)
    write_sandbox({**repo, "profile": data})
    return store.get("repos", repo_id) or repo


def now() -> str:
    return datetime.now(timezone.utc).isoformat()
