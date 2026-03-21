"""Run a backend health check for the selected profile."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backends.router import BackendRouter
from core.backend_config import select_backend_config
from core.config_loader import ConfigLoader


def main() -> int:
    """CLI entrypoint."""

    parser = argparse.ArgumentParser(description="Run backend health check.")
    parser.add_argument("--profile", default="basic", help="Profile to load")
    args = parser.parse_args()

    settings, _, _ = ConfigLoader().load(args.profile)
    backend_config = select_backend_config(settings)
    router = BackendRouter()
    result = router.health_check(
        backend_config.provider,
        {
            "endpoint": backend_config.endpoint,
            "model": backend_config.model,
            "timeout_seconds": backend_config.options.get("timeout_seconds", 30),
            "api_key": backend_config.options.get("api_key", ""),
        },
    )

    print(f"Provider: {result.provider}")
    print(f"Status: {result.status}")
    print(f"OK: {result.ok}")
    print(f"Message: {result.message}")
    if result.details:
        print(f"Details: {result.details}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
