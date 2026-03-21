"""Base backend adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from core.backend_types import BackendEvent, BackendRequest, BackendResponse, HealthCheckResult, StreamingChunk


class BaseBackendAdapter(ABC):
    """Common interface implemented by every backend provider."""

    provider_name: str

    def __init__(self, provider_name: str, config: dict[str, Any] | None = None) -> None:
        self.provider_name = provider_name
        self.config = config or {}

    @abstractmethod
    def chat(self, request: BackendRequest) -> BackendResponse:
        """Run a non-streaming chat request."""

    @abstractmethod
    def stream_chat(self, request: BackendRequest) -> Iterator[StreamingChunk]:
        """Run a streaming chat request."""

    @abstractmethod
    def health_check(self) -> HealthCheckResult:
        """Check whether the backend is reachable and usable."""

    @abstractmethod
    def current_status(self) -> str:
        """Return current backend status."""

    def emit_event(self, event_type: str, status: str, message: str, payload: dict | None = None) -> BackendEvent:
        """Build a standard backend event."""

        return BackendEvent(
            event_type=event_type,  # type: ignore[arg-type]
            provider=self.provider_name,
            status=status,  # type: ignore[arg-type]
            message=message,
            payload=payload or {},
        )
