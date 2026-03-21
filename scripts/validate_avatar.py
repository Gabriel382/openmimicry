
"""Validate an avatar pack from the command line."""

from __future__ import annotations

from pathlib import Path
import argparse
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from avatar.validation import validate_avatar_pack  # noqa: E402


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Validate an OpenMimicry avatar pack.")
    parser.add_argument("--pack-root", required=True, help="Path to the avatar pack root.")
    args = parser.parse_args()

    result = validate_avatar_pack(Path(args.pack_root))
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
