"""Backend router selecting the active provider from config."""

from __future__ import annotations

from collections.abc import Iterator

from backends.base import BaseBackendAdapter
from backends.mock_backend import MockBackendAdapter
from core.backend_types import BackendEvent, BackendRequest, BackendResponse, HealthCheckResult, StreamingChunk


class BackendRouter:
    """Resolve and execute the configured backend provider."""

    def __init__(self) -> None:
        self._factories: dict[str, type[BaseBackendAdapter]] = {
            "mock": MockBackendAdapter,
        }
        self._events: list[BackendEvent] = []

    def register(self, provider_name: str, adapter_cls: type[BaseBackendAdapter]) -> None:
        """Register a backend adapter class under a provider name."""

        self._factories[provider_name] = adapter_cls

    def available_backends(self) -> list[str]:
        """Return the list of registered providers."""

        return sorted(self._factories.keys())

    def create_adapter(self, provider_name: str) -> BaseBackendAdapter:
        """Instantiate the selected backend adapter."""

        if provider_name not in self._factories:
            supported = ", ".join(self.available_backends())
            raise ValueError(f"Unknown backend provider '{provider_name}'. Available: {supported}")
        adapter = self._factories[provider_name]()
        self._events.append(adapter.emit_event("backend.selected", adapter.current_status(), f"Selected backend '{provider_name}'."))
        return adapter

    def chat(self, provider_name: str, request: BackendRequest) -> BackendResponse:
        """Run a non-streaming chat request through the selected backend."""

        adapter = self.create_adapter(provider_name)
        self._events.append(adapter.emit_event("backend.request.started", adapter.current_status(), "Chat request started."))
        response = adapter.chat(request)
        self._events.append(adapter.emit_event("backend.request.finished", adapter.current_status(), "Chat request finished."))
        return response

    def stream_chat(self, provider_name: str, request: BackendRequest) -> Iterator[StreamingChunk]:
        """Run a streaming chat request through the selected backend."""

        adapter = self.create_adapter(provider_name)
        self._events.append(adapter.emit_event("backend.request.started", adapter.current_status(), "Streaming request started."))
        for chunk in adapter.stream_chat(request):
            self._events.append(
                adapter.emit_event(
                    "backend.stream.delta",
                    adapter.current_status(),
                    "Streaming chunk received.",
                    payload={"delta": chunk.delta, "done": chunk.done},
                )
            )
            yield chunk
        self._events.append(adapter.emit_event("backend.request.finished", adapter.current_status(), "Streaming request finished."))

    def health_check(self, provider_name: str) -> HealthCheckResult:
        """Run the configured provider health check."""

        adapter = self.create_adapter(provider_name)
        result = adapter.health_check()
        event_type = "backend.health.ok" if result.ok else "backend.health.failed"
        self._events.append(adapter.emit_event(event_type, result.status, result.message, payload=result.details))
        return result

    def events(self) -> list[BackendEvent]:
        """Return accumulated router events."""

        return list(self._events)
