"""CLI health check for the currently selected backend."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backends.router import BackendRouter
from core.backend_config import select_backend_config
from core.config_loader import ConfigLoader


def main() -> int:
    parser = argparse.ArgumentParser(description="Run backend health checks.")
    parser.add_argument("--profile", default=os.getenv("OPENMIMICRY_PROFILE", "basic"))
    args = parser.parse_args()

    loader = ConfigLoader()
    settings, _, _ = loader.load(args.profile)
    backend_config = select_backend_config(settings)

    router = BackendRouter()
    result = router.health_check(backend_config.provider)

    print(f"Provider: {result.provider}")
    print(f"Status: {result.status}")
    print(f"Healthy: {result.ok}")
    print(f"Message: {result.message}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
