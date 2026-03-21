"""Mock backend used for local testing and early UI work."""

from __future__ import annotations

from collections.abc import Iterator

from backends.base import BaseBackendAdapter
from core.backend_types import BackendRequest, BackendResponse, HealthCheckResult, StreamingChunk


class MockBackendAdapter(BaseBackendAdapter):
    """Very small backend that echoes the last user message."""

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(provider_name="mock", config=config)
        self._status = "ready"

    def chat(self, request: BackendRequest) -> BackendResponse:
        last_message = request.messages[-1].content if request.messages else ""
        text = f"[mock] Echo: {last_message}" if last_message else "[mock] No input received."
        return BackendResponse(
            text=text,
            model=request.model or "mock-model",
            provider=self.provider_name,
            usage={"prompt_tokens": 0, "completion_tokens": 0},
        )

    def stream_chat(self, request: BackendRequest) -> Iterator[StreamingChunk]:
        response = self.chat(request)
        words = response.text.split()
        for index, word in enumerate(words):
            yield StreamingChunk(
                delta=(word + (" " if index < len(words) - 1 else "")),
                done=False,
                model=response.model,
                provider=self.provider_name,
            )
        yield StreamingChunk(delta="", done=True, model=response.model, provider=self.provider_name)

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(
            ok=True,
            status="ready",
            message="Mock backend is always available.",
            provider=self.provider_name,
        )

    def current_status(self) -> str:
        return self._status
