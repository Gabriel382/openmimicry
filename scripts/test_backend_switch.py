"""CLI utility to validate backend switching and request routing."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backends.router import BackendRouter
from core.backend_types import BackendMessage, BackendRequest
from core.config_loader import ConfigLoader


def main() -> int:
    parser = argparse.ArgumentParser(description="Test backend switching.")
    parser.add_argument("--profile", default=os.getenv("OPENMIMICRY_PROFILE", "basic"))
    parser.add_argument("--provider", default=None, help="Override backend provider for the test.")
    parser.add_argument("--message", default="Hello from OpenMimicry")
    args = parser.parse_args()

    loader = ConfigLoader()
    settings, _, _ = loader.load(args.profile)
    provider = args.provider or settings.backend_provider

    router = BackendRouter()
    request = BackendRequest(
        messages=[BackendMessage(role="user", content=args.message)],
        model=settings.model_name,
        stream=False,
        metadata={"profile": settings.profile},
    )
    response = router.chat(provider, request)

    print(f"Selected provider: {provider}")
    print(f"Response model: {response.model}")
    print(f"Response text: {response.text}")
    print("Events:")
    for event in router.events():
        print(f"- {event.timestamp} | {event.event_type} | {event.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
