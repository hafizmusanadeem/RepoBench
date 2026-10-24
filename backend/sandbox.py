"""Generate a Dockerfile + compose.yaml per cloned repo (replaces the
hand-written sandbox/<name>/ directories) and build the image.

Dependencies are installed at BUILD time (network on); the compose service runs
with network_mode: none, so agents cannot reach the internet during a run.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .config import REPOS_DIR, SANDBOX_DIR
from .schemas import Profile

_DOCKERFILE = """# syntax=docker/dockerfile:1
FROM {base_image}
RUN apt-get update && apt-get install -y --no-install-recommends \\
        git build-essential curl ca-certificates \\
    && rm -rf /var/lib/apt/lists/*
COPY . /repo
WORKDIR /repo
RUN git config --global --add safe.directory /repo
{install_block}
# Files the install step created but .gitignore doesn't cover must not show up
# in the agent's diff.
RUN git ls-files --others --exclude-standard >> .git/info/exclude || true
CMD ["tail", "-f", "/dev/null"]
"""


def sandbox_dir(repo_id: str) -> Path:
    return SANDBOX_DIR / repo_id


def write_sandbox(repo: dict) -> Path:
    """(Re)write Dockerfile + compose.yaml from the repo's current profile and
    return the compose path."""
    profile = Profile.model_validate(repo["profile"])
    d = sandbox_dir(repo["id"])
    d.mkdir(parents=True, exist_ok=True)

    cmd = profile.install_command.strip()
    install_block = f"RUN <<'EOF'\nset -e\n{cmd}\nEOF" if cmd else ""
    (d / "Dockerfile").write_text(_DOCKERFILE.format(base_image=profile.base_image, install_block=install_block))

    context = (REPOS_DIR / repo["id"]).resolve()
    # JSON strings are valid YAML scalars, which handles paths with spaces.
    compose = f"""services:
  default:
    image: {json.dumps("repobench-" + repo["id"])}
    build:
      context: {json.dumps(str(context))}
      dockerfile: {json.dumps(str((d / "Dockerfile").resolve()))}
    init: true
    command: tail -f /dev/null
    cpus: 2.0
    mem_limit: 4gb
    network_mode: none
"""
    path = d / "compose.yaml"
    path.write_text(compose)
    return path


async def build_image(compose_path: Path) -> tuple[bool, str]:
    proc = await asyncio.create_subprocess_exec(
        "docker", "compose", "-f", str(compose_path), "build",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    return proc.returncode == 0, out.decode(errors="replace")[-4000:]
