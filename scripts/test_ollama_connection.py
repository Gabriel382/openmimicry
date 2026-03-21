"""Test the Ollama connection directly."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backends.ollama_backend import OllamaBackendAdapter
from core.config_loader import ConfigLoader
from core.backend_config import select_backend_config


def main() -> int:
    """CLI entrypoint."""

    parser = argparse.ArgumentParser(description="Test the Ollama backend connection.")
    parser.add_argument("--profile", default="basic", help="Profile to load")
    args = parser.parse_args()

    settings, _, _ = ConfigLoader().load(args.profile)
    backend_config = select_backend_config(settings)

    adapter = OllamaBackendAdapter(
        {
            "endpoint": backend_config.endpoint,
            "model": backend_config.model,
            "timeout_seconds": backend_config.options.get("timeout_seconds", 30),
        }
    )
    result = adapter.health_check()

    print(f"Endpoint: {backend_config.endpoint}")
    print(f"Model: {backend_config.model}")
    print(f"OK: {result.ok}")
    print(f"Status: {result.status}")
    print(f"Message: {result.message}")
    if result.details:
        print(f"Details: {result.details}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
