
"""Structured JSON-like response schema for backend-driven avatar actions."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(slots=True)
class AvatarAction:
    """High-level avatar action returned by a backend or director layer."""

    state: str
    emotion: str
    animation: str
    next_state: str = "idle"
    duration_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return asdict(self)


@dataclass(slots=True)
class BackendAvatarResponse:
    """Combined textual and avatar response payload."""

    text: str
    avatar: AvatarAction
    backend: str = "mock"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        payload = asdict(self)
        return payload
