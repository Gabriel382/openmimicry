"""Helpers for selecting backend configuration from runtime settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.types import RuntimeSettings


@dataclass(slots=True)
class SelectedBackendConfig:
    """Normalized backend configuration consumed by the router and CLI tools."""

    provider: str
    endpoint: str
    model: str
    options: dict[str, Any]


def select_backend_config(settings: RuntimeSettings) -> SelectedBackendConfig:
    """Build a normalized backend config from runtime settings."""

    return SelectedBackendConfig(
        provider=settings.backend_provider,
        endpoint=settings.backend_endpoint,
        model=settings.model_name,
        options={
            "profile": settings.profile,
            "log_level": settings.log_level,
            "overlay_enabled": settings.overlay_enabled,
            "avatar_runtime": settings.avatar_runtime,
            "timeout_seconds": settings.backend_options.get("timeout_seconds", 30),
            "stream": settings.backend_options.get("stream", True),
            "api_key": settings.backend_options.get("api_key"),
        },
    )
