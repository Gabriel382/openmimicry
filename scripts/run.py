"""Minimal runtime entrypoint using the backend router."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backends.router import BackendRouter
from core.backend_config import select_backend_config
from core.backend_types import BackendMessage, BackendRequest
from core.config_loader import ConfigLoader


def _print_events(router: BackendRouter) -> None:
    """Print backend events for debugging."""

    print("Runtime events:")
    for event in router.events():
        print(f"  - [{event.provider}] {event.event_type}: {event.message}")


def main() -> int:
    """Run the minimal app bootstrap and execute one request."""

    profile = os.getenv("OPENMIMICRY_PROFILE", "basic")
    loader = ConfigLoader()
    settings, packages, extras = loader.load(profile)
    backend_config = select_backend_config(settings)

    router = BackendRouter()
    request = BackendRequest(
        messages=[BackendMessage(role="user", content="Hello OpenMimicry")],
        model=backend_config.model,
        stream=bool(backend_config.options.get("stream", False)),
        metadata={"profile": settings.profile},
    )

    adapter_config = {
        "endpoint": backend_config.endpoint,
        "model": backend_config.model,
        "timeout_seconds": backend_config.options.get("timeout_seconds", 30),
        "api_key": backend_config.options.get("api_key", ""),
    }

    health = router.health_check(backend_config.provider, adapter_config)
    if health.ok and request.stream:
        chunks = []
        for chunk in router.stream_chat(backend_config.provider, request, adapter_config):
            if chunk.delta:
                chunks.append(chunk.delta)
        text = "".join(chunks).strip()
        active_provider = backend_config.provider
    else:
        response = router.chat(backend_config.provider, request, adapter_config)
        text = response.text
        active_provider = response.provider

    print(f"Starting {settings.app_name}")
    print(f"Profile: {settings.profile}")
    print(f"Configured backend: {backend_config.provider} @ {backend_config.endpoint}")
    print(f"Active backend: {active_provider}")
    print(f"Model: {backend_config.model}")
    print(f"Avatar runtime: {settings.avatar_runtime}")
    print(f"Resolved packages: {', '.join(packages)}")
    print(f"Resolved extras: {', '.join(extras) if extras else 'none'}")
    print(f"Backend response: {text}")
    _print_events(router)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
