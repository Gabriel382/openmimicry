"""Test switching between registered backends."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backends.router import BackendRouter
from core.backend_config import select_backend_config
from core.backend_types import BackendMessage, BackendRequest
from core.config_loader import ConfigLoader


def main() -> int:
    """CLI entrypoint."""

    parser = argparse.ArgumentParser(description="Test backend switching.")
    parser.add_argument("--profile", default="basic", help="Profile to load")
    args = parser.parse_args()

    settings, _, _ = ConfigLoader().load(args.profile)
    backend_config = select_backend_config(settings)
    router = BackendRouter()

    request = BackendRequest(
        messages=[BackendMessage(role="user", content="Ping from switch test")],
        model=backend_config.model,
    )

    print("Available backends:", ", ".join(router.available_backends()))
    for provider in router.available_backends():
        response = router.chat(
            provider,
            request,
            {
                "endpoint": backend_config.endpoint,
                "model": backend_config.model,
                "timeout_seconds": backend_config.options.get("timeout_seconds", 30),
            },
        )
        print(f"[{provider}] -> active provider: {response.provider} | text: {response.text}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
