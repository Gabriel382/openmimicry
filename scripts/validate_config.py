"""Validate config and print the resolved runtime/package state."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config_loader import ConfigLoader
from core.validation import ConfigValidationError


def main() -> int:
    """CLI entrypoint."""

    parser = argparse.ArgumentParser(description="Validate and print resolved OpenMimicry config.")
    parser.add_argument("--profile", default="basic", help="Profile to validate")
    args = parser.parse_args()

    try:
        loader = ConfigLoader()
        settings, packages, extras = loader.load(args.profile)
    except ConfigValidationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    output = {
        "runtime_settings": asdict(settings),
        "packages": packages,
        "extras": extras,
    }
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
