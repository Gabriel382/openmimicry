
"""Run the OpenMimicry 6.5 animated 2D character demo."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from avatar.animated_runtime_2d import AnimatedAvatar2DRuntime  # noqa: E402
from backends.simple_json_backend import SimpleBackendConfig  # noqa: E402


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Run OpenMimicry animated character demo.")
    parser.add_argument(
        "--character-root",
        default=str(PROJECT_ROOT / "characters" / "octomimic"),
        help="Path to the character root.",
    )
    parser.add_argument(
        "--provider",
        default="ollama",
        choices=["ollama", "mock"],
        help="Backend provider for the demo.",
    )
    parser.add_argument(
        "--endpoint",
        default="http://localhost:11434",
        help="Backend endpoint.",
    )
    parser.add_argument(
        "--model",
        default="qwen2.5:1.5b-instruct-q4_K_M",
        help="Model name for Ollama.",
    )
    parser.add_argument(
        "--disable-tts",
        action="store_true",
        help="Disable local text-to-speech playback.",
    )
    args = parser.parse_args()

    config = SimpleBackendConfig(
        provider=args.provider,
        endpoint=args.endpoint,
        model=args.model,
        fallback_to_mock=True,
    )
    runtime = AnimatedAvatar2DRuntime(
        character_root=Path(args.character_root),
        backend_config=config,
        enable_tts=not args.disable_tts,
    )
    runtime.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
