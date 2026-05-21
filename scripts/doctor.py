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


def _check_vision_stack() -> None:
    """Soft checks for the M13 vision stack.

    Everything here is optional. The function only **warns**: vision
    is gated behind ``vision.enabled=true`` in config and is never
    required to run the rest of OpenMimicry.
    """
    try:
        import importlib

        importlib.import_module("openmimicry.vision")
        print(f"  {CHECK} openmimicry-vision: importable")
    except Exception as exc:  # noqa: BLE001
        print(f"  {WARN} openmimicry-vision: not importable ({exc})")
        return

    try:
        cv2 = __import__("cv2")
        print(f"  {CHECK} OpenCV: {getattr(cv2, '__version__', '?')}")
    except Exception:  # noqa: BLE001
        print(
            f"  {WARN} OpenCV not installed "
            "(pip install \"openmimicry-vision[mediapipe]\")"
        )

    try:
        mediapipe = __import__("mediapipe")
        print(f"  {CHECK} MediaPipe: {getattr(mediapipe, '__version__', '?')}")
    except Exception:  # noqa: BLE001
        print(
            f"  {WARN} MediaPipe not installed "
            "(pip install \"openmimicry-vision[mediapipe]\")"
        )

    # Camera-index probe (best-effort, never raises). We only attempt
    # this when the env opt-in is set so running `make doctor` doesn't
    # yank the webcam on.
    if os.environ.get("OPENMIMICRY_DOCTOR_PROBE_CAMERA") == "1":
        try:
            cv2 = __import__("cv2")
            cap = cv2.VideoCapture(0)
            opened = cap.isOpened()
            cap.release()
            if opened:
                print(f"  {CHECK} camera index 0: opens")
            else:
                print(f"  {WARN} camera index 0: failed to open")
        except Exception as exc:  # noqa: BLE001
            print(f"  {WARN} camera probe raised: {exc}")
    else:
        print(
            f"  {WARN} camera probe skipped "
            "(set OPENMIMICRY_DOCTOR_PROBE_CAMERA=1 to enable)"
        )


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

    print("\nVision (M13 — optional, off by default):")
    _check_vision_stack()

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
    _check_path("packages/openmimicry-vision", REPO_ROOT / "packages" / "openmimicry-vision")
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
