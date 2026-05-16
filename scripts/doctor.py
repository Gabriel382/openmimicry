#!/usr/bin/env python3
"""`make doctor` — print a readable checklist of the dev environment.

Cross-platform so Windows and Linux contributors get the same output.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CHECK = "[ OK ]"
WARN = "[WARN]"
FAIL = "[FAIL]"


def _run(cmd: list[str]) -> str | None:
    """Run a command, return its first line of stdout, or None if missing."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    line = (result.stdout or result.stderr).strip().splitlines()
    return line[0] if line else ""


def _check(label: str, cmd: list[str], *, required: bool = False) -> bool:
    if shutil.which(cmd[0]) is None:
        marker = FAIL if required else WARN
        print(f"  {marker} {label}: not found on PATH")
        return False
    version = _run(cmd) or "(version unknown)"
    print(f"  {CHECK} {label}: {version}")
    return True


def _check_env(name: str, *, required: bool = False) -> bool:
    if os.environ.get(name):
        print(f"  {CHECK} env {name}: set")
        return True
    marker = FAIL if required else WARN
    print(f"  {marker} env {name}: not set")
    return False


def _check_path(label: str, path: Path, *, required: bool = False) -> bool:
    if path.exists():
        print(f"  {CHECK} {label}: {path}")
        return True
    marker = FAIL if required else WARN
    print(f"  {marker} {label}: missing ({path})")
    return False


def main() -> int:
    print("OpenMimicry doctor")
    print("=" * 60)
    failures = 0

    print("\nLanguages and toolchains:")
    if not _check("Python", [sys.executable, "--version"], required=True):
        failures += 1
    _check("Node", ["node", "--version"])
    _check("npm", ["npm", "--version"])
    _check("Rust", ["rustc", "--version"])
    _check("Cargo", ["cargo", "--version"])

    print("\nDeveloper tools:")
    _check("Ruff", ["ruff", "--version"])
    _check("Pyright", ["pyright", "--version"])
    _check("pytest", ["pytest", "--version"])
    _check("pre-commit", ["pre-commit", "--version"])

    print("\nOptional runtime tools:")
    _check("ffmpeg", ["ffmpeg", "-version"])
    _check("ollama", ["ollama", "--version"])
    _check("tauri", ["cargo", "tauri", "--version"])

    print("\nEnvironment:")
    _check_env("OPENROUTER_API_KEY")
    _check_env("OLLAMA_API_KEY")
    _check_env("OPENMIMICRY_PROFILE")

    print("\nRepo layout:")
    if not _check_path("workspace pyproject.toml", REPO_ROOT / "pyproject.toml", required=True):
        failures += 1
    if not _check_path("contracts", REPO_ROOT / "docs" / "contracts.md", required=True):
        failures += 1
    _check_path("packages/openmimicry-core", REPO_ROOT / "packages" / "openmimicry-core")
    _check_path("frontend/", REPO_ROOT / "frontend")
    _check_path("src-tauri/", REPO_ROOT / "src-tauri")

    print("\n" + "=" * 60)
    if failures:
        print(f"{FAIL} {failures} required check(s) failed")
        return 1
    print(f"{CHECK} environment looks workable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
