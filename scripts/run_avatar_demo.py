
"""Run a simple local 2D avatar demo."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from avatar.runtime_2d import Avatar2DRuntime  # noqa: E402


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Run OpenMimicry 2D avatar demo.")
    parser.add_argument(
        "--packs-root",
        default=str(PROJECT_ROOT / "packs"),
        help="Path to the packs directory.",
    )
    parser.add_argument(
        "--pack-name",
        default="avatar_2d_demo",
        help="Avatar pack name to run.",
    )
    args = parser.parse_args()

    runtime = Avatar2DRuntime(
        packs_root=Path(args.packs_root),
        pack_name=args.pack_name,
    )
    runtime.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
