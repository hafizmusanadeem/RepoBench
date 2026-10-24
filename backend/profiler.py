"""Detect a repository's language, install command and test command.

Pure heuristics from marker files (~100 lines on purpose). The result is only a
starting point: the UI shows it as editable fields before any run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _read(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def _python(root: Path) -> dict[str, Any]:
    version = _read(root / ".python-version").strip().split("\n")[0] or "3.12"
    if not re.fullmatch(r"\d+\.\d+", version):
        version = "3.12"
    install = [
        "pip install --no-cache-dir pytest",
        '(pip install --no-cache-dir -e ".[dev,test]" || pip install --no-cache-dir -e . || true)',
    ]
    if (root / "requirements.txt").exists():
        install.append("pip install --no-cache-dir -r requirements.txt")
    return {
        "language": "python",
        "package_manager": "uv" if (root / "uv.lock").exists() else "pip",
        "base_image": f"python:{version}-slim",
        "install_command": "\n".join(install),
        "test_command": "python -m pytest -q -rf",
        "build_command": "",
        "lint_command": "ruff check . 2>/dev/null || true",
        "notes": ["Python install is a guess (pip -e with dev/test extras). Edit it if your repo needs more."],
    }


def _node(root: Path) -> dict[str, Any]:
    try:
        pkg = json.loads(_read(root / "package.json") or "{}")
    except json.JSONDecodeError:
        pkg = {}
    if (root / "pnpm-lock.yaml").exists():
        mgr, install, test = "pnpm", "corepack enable && pnpm install --frozen-lockfile", "pnpm test"
    elif (root / "yarn.lock").exists():
        mgr, install, test = "yarn", "corepack enable && yarn install --frozen-lockfile", "yarn test"
    else:
        mgr, install, test = "npm", "npm ci || npm install", "npm test --silent"
    notes = []
    if "test" not in (pkg.get("scripts") or {}):
        test = ""
        notes.append("package.json has no 'test' script; add a test command so regressions can be detected.")
    return {
        "language": "node", "package_manager": mgr, "base_image": "node:22-bookworm-slim",
        "install_command": install, "test_command": test,
        "build_command": "npm run build" if test else "",
        "lint_command": "",
        "notes": notes,
    }


def profile_repo(root: Path) -> dict[str, Any]:
    if (root / "package.json").exists():
        return _node(root)
    if any((root / f).exists() for f in ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt")):
        return _python(root)
    if (root / "go.mod").exists():
        return {"language": "go", "package_manager": "go", "base_image": "golang:1.23-bookworm",
                "install_command": "go mod download", "test_command": "go test ./...",
                "build_command": "go build ./...", "lint_command": "",
                "notes": []}
    if (root / "Cargo.toml").exists():
        return {"language": "rust", "package_manager": "cargo", "base_image": "rust:1-bookworm",
                "install_command": "cargo build --tests", "test_command": "cargo test --offline",
                "build_command": "cargo build --offline", "lint_command": "",
                "notes": []}
    if (root / "pom.xml").exists():
        return {"language": "java", "package_manager": "maven", "base_image": "maven:3.9-eclipse-temurin-21",
                "install_command": "mvn -q dependency:go-offline", "test_command": "mvn -q -o test",
                "build_command": "mvn -q -o package -DskipTests", "lint_command": "",
                "notes": []}
    return {"language": "unknown", "package_manager": "", "base_image": "ubuntu:24.04", "install_command": "",
            "test_command": "", "build_command": "", "lint_command": "",
            "notes": ["Could not detect the language. Fill in every field below."]}
