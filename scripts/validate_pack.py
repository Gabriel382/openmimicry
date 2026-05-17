#!/usr/bin/env python3
"""CLI: validate one or more character packs.

Wraps ``openmimicry.avatar.pack.validate_pack``. Exit code 0 on success
(all packs valid, warnings allowed), 1 on any pack with errors.

Examples:

    python scripts/validate_pack.py characters/octomimic/
    python scripts/validate_pack.py characters/*/
    python scripts/validate_pack.py --strict characters/      # warnings -> errors

Used by ``make validate-packs`` and by the CI ``pack-lint`` job.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from openmimicry.avatar.pack import validate_pack


def _collect_packs(args: argparse.Namespace) -> list[Path]:
    out: list[Path] = []
    for raw in args.paths:
        p = Path(raw).expanduser()
        if (p / "pack.yaml").is_file():
            out.append(p)
            continue
        if p.is_dir():
            # Treat as a roots directory: every subdir with a pack.yaml.
            for child in sorted(p.iterdir()):
                if child.is_dir() and (child / "pack.yaml").is_file():
                    out.append(child)
            continue
        out.append(p)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate one or more OpenMimicry character packs."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Pack directories OR directories containing pack subdirectories.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings (e.g. missing speaking_frames) as errors.",
    )
    args = parser.parse_args(argv)

    packs = _collect_packs(args)
    if not packs:
        print("no packs found", file=sys.stderr)
        return 1

    failures = 0
    for pack_path in packs:
        report = validate_pack(pack_path)
        print(report.summary())
        for err in report.errors:
            print(f"  ERROR: {err}", file=sys.stderr)
        for warn in report.warnings:
            print(f"  WARN:  {warn}", file=sys.stderr)
        if not report.ok or (args.strict and report.warnings):
            failures += 1

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
