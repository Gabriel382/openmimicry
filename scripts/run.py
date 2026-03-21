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


def main() -> int:
    """Run the minimal app bootstrap and execute one mock request."""

    profile = os.getenv("OPENMIMICRY_PROFILE", "basic")
    loader = ConfigLoader()
    settings, packages, extras = loader.load(profile)
    backend_config = select_backend_config(settings)

    router = BackendRouter()
    request = BackendRequest(
        messages=[BackendMessage(role="user", content="Hello OpenMimicry")],
        model=backend_config.model,
        stream=False,
        metadata={"profile": settings.profile},
    )
    response = router.chat(backend_config.provider, request)

    print(f"Starting {settings.app_name}")
    print(f"Profile: {settings.profile}")
    print(f"Backend: {backend_config.provider} @ {backend_config.endpoint}")
    print(f"Model: {backend_config.model}")
    print(f"Avatar runtime: {settings.avatar_runtime}")
    print(f"Resolved packages: {', '.join(packages)}")
    print(f"Resolved extras: {', '.join(extras) if extras else 'none'}")
    print(f"Backend response: {response.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
