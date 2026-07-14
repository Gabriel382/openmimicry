"""Install the dependencies for a selected OpenMimicry profile."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Ensure local imports work when running from repository root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config_loader import ConfigLoader
from core.validation import ConfigValidationError


def run_command(command: list[str]) -> None:
    """Run a subprocess and fail loudly on error."""

    print("[install]", " ".join(command))
    subprocess.run(command, check=True)


def main() -> int:
    """CLI entrypoint."""

    parser = argparse.ArgumentParser(description="Install a profile and its dependencies.")
    parser.add_argument("--profile", default="basic", help="Profile to install")
    args = parser.parse_args()

    try:
        loader = ConfigLoader()
        settings, packages, extras = loader.load(args.profile)
    except ConfigValidationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    print(f"Resolved profile: {settings.profile}")
    print(f"Avatar runtime: {settings.avatar_runtime}")
    print(f"Packages: {', '.join(packages)}")
    print(f"Python extras: {', '.join(extras) if extras else 'none'}")

    extras_expr = f".[{','.join(extras)}]" if extras else "."
    run_command([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    run_command([sys.executable, "-m", "pip", "install", "-e", extras_expr])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
