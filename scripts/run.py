"""Very small runtime entrypoint for Milestone 1."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config_loader import ConfigLoader


def main() -> int:
    """Run the minimal app bootstrap."""

    profile = os.getenv("OPENMIMICRY_PROFILE", "basic")
    loader = ConfigLoader()
    settings, packages, extras = loader.load(profile)

    print(f"Starting {settings.app_name}")
    print(f"Profile: {settings.profile}")
    print(f"Backend: {settings.backend_provider} @ {settings.backend_endpoint}")
    print(f"Model: {settings.model_name}")
    print(f"Avatar runtime: {settings.avatar_runtime}")
    print(f"Resolved packages: {', '.join(packages)}")
    print(f"Resolved extras: {', '.join(extras) if extras else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
