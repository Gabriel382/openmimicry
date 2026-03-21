"""Standalone demo launcher for the simple 2D avatar runtime."""

from __future__ import annotations
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse

from avatar.runtime_2d import Avatar2DRuntime


def main() -> None:
    """Launch the demo avatar runtime."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--avatar-root",
        default="packs/avatar_2d_demo",
        help="Path to the avatar pack directory.",
    )
    args = parser.parse_args()

    runtime = Avatar2DRuntime(avatar_root=Path(args.avatar_root))
    runtime.demo_cycle()
    runtime.run()


if __name__ == "__main__":
    main()
