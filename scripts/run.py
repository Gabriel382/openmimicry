"""Minimal placeholder entrypoint for Milestone 0."""

from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    print("OpenMimicry placeholder app")
    print(f"Project root: {root}")


if __name__ == "__main__":
    main()
