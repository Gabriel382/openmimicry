"""Typed models used by the backend adapter layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


BackendEventType = Literal[
    "backend.selected",
    "backend.connected",
    "backend.disconnected",
    "backend.health.ok",
    "backend.health.failed",
    "backend.request.started",
    "backend.request.finished",
    "backend.stream.delta",
    "backend.error",
]

BackendStatus = Literal["unknown", "ready", "busy", "degraded", "offline"]
BackendRole = Literal["system", "user", "assistant", "tool"]


@dataclass(slots=True)
class BackendMessage:
    """A single chat message passed to a backend."""

    role: BackendRole
    content: str


@dataclass(slots=True)
class BackendRequest:
    """Standard request payload understood by every backend adapter."""

    messages: list[BackendMessage]
    model: str | None = None
    stream: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BackendResponse:
    """Non-streaming response payload returned by a backend."""

    text: str
    model: str
    provider: str
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StreamingChunk:
    """Single streaming chunk produced by a backend."""

    delta: str
    done: bool = False
    model: str | None = None
    provider: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class HealthCheckResult:
    """Health status returned by a backend health check."""

    ok: bool
    status: BackendStatus
    message: str
    provider: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BackendEvent:
    """Runtime event emitted by backend adapters and router."""

    event_type: BackendEventType
    provider: str
    status: BackendStatus
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: dict[str, Any] = field(default_factory=dict)
