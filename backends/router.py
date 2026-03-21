"""Backend router selecting the active provider from config."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from backends.base import BaseBackendAdapter
from backends.mock_backend import MockBackendAdapter
from backends.ollama_backend import OllamaBackendAdapter
from core.backend_types import BackendEvent, BackendRequest, BackendResponse, HealthCheckResult, StreamingChunk


class BackendRouter:
    """Resolve and execute the configured backend provider."""

    def __init__(self) -> None:
        self._factories: dict[str, type[BaseBackendAdapter]] = {
            "mock": MockBackendAdapter,
            "ollama": OllamaBackendAdapter,
        }
        self._events: list[BackendEvent] = []

    def register(self, provider_name: str, adapter_cls: type[BaseBackendAdapter]) -> None:
        """Register a backend adapter class under a provider name."""

        self._factories[provider_name] = adapter_cls

    def available_backends(self) -> list[str]:
        """Return the list of registered providers."""

        return sorted(self._factories.keys())

    def create_adapter(self, provider_name: str, adapter_config: dict[str, Any] | None = None) -> BaseBackendAdapter:
        """Instantiate the selected backend adapter."""

        if provider_name not in self._factories:
            supported = ", ".join(self.available_backends())
            raise ValueError(f"Unknown backend provider '{provider_name}'. Available: {supported}")
        adapter = self._factories[provider_name](adapter_config)
        self._events.append(
            adapter.emit_event(
                "backend.selected",
                adapter.current_status(),
                f"Selected backend '{provider_name}'.",
                payload={"config": adapter_config or {}},
            )
        )
        return adapter

    def _fallback_chat(self, request: BackendRequest, reason: str, adapter_config: dict[str, Any] | None = None) -> BackendResponse:
        """Fall back to mock backend and log the transition."""

        fallback = MockBackendAdapter(adapter_config)
        self._events.append(
            fallback.emit_event(
                "backend.fallback",
                fallback.current_status(),
                reason,
            )
        )
        return fallback.chat(request)

    def chat(self, provider_name: str, request: BackendRequest, adapter_config: dict[str, Any] | None = None) -> BackendResponse:
        """Run a non-streaming chat request through the selected backend."""

        adapter = self.create_adapter(provider_name, adapter_config)
        self._events.append(adapter.emit_event("backend.request.started", adapter.current_status(), "Chat request started."))
        try:
            response = adapter.chat(request)
            self._events.append(
                adapter.emit_event(
                    "backend.log",
                    adapter.current_status(),
                    "Chat response received.",
                    payload={"model": response.model, "provider": response.provider},
                )
            )
            self._events.append(adapter.emit_event("backend.request.finished", adapter.current_status(), "Chat request finished."))
            return response
        except Exception as exc:
            self._events.append(adapter.emit_event("backend.error", "degraded", f"Backend request failed: {exc}"))
            return self._fallback_chat(request, f"Falling back to mock backend because '{provider_name}' failed: {exc}", adapter_config)

    def stream_chat(self, provider_name: str, request: BackendRequest, adapter_config: dict[str, Any] | None = None) -> Iterator[StreamingChunk]:
        """Run a streaming chat request through the selected backend."""

        adapter = self.create_adapter(provider_name, adapter_config)
        self._events.append(adapter.emit_event("backend.request.started", adapter.current_status(), "Streaming request started."))
        try:
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
        except Exception as exc:
            self._events.append(adapter.emit_event("backend.error", "degraded", f"Streaming request failed: {exc}"))
            for chunk in MockBackendAdapter(adapter_config).stream_chat(request):
                yield chunk

    def health_check(self, provider_name: str, adapter_config: dict[str, Any] | None = None) -> HealthCheckResult:
        """Run the configured provider health check."""

        adapter = self.create_adapter(provider_name, adapter_config)
        result = adapter.health_check()
        event_type = "backend.health.ok" if result.ok else "backend.health.failed"
        self._events.append(adapter.emit_event(event_type, result.status, result.message, payload=result.details))
        return result

    def events(self) -> list[BackendEvent]:
        """Return accumulated router events."""

        return list(self._events)
