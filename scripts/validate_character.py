
"""Validate an animated character pack."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from avatar.animated_validation import validate_character_pack  # noqa: E402


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Validate an OpenMimicry character pack.")
    parser.add_argument("--character-root", required=True, help="Path to character root.")
    args = parser.parse_args()

    result = validate_character_pack(Path(args.character_root))
    print(f"OK: {result.ok}")

    if result.errors:
        print("Errors:")
        for error in result.errors:
            print(f"  - {error}")

    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
