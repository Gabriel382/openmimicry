"""Ollama backend adapter."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import requests

from backends.base import BaseBackendAdapter
from core.backend_types import BackendRequest, BackendResponse, HealthCheckResult, StreamingChunk


class OllamaBackendAdapter(BaseBackendAdapter):
    """Backend adapter using Ollama's local HTTP API."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(provider_name="ollama", config=config)
        self._status = "unknown"
        self.endpoint = str(self.config.get("endpoint", "http://localhost:11434")).rstrip("/")
        self.model = str(self.config.get("model", "qwen2.5:7b"))
        self.timeout = int(self.config.get("timeout_seconds", 30))
        self.session = requests.Session()

    def _messages_payload(self, request: BackendRequest) -> list[dict[str, str]]:
        """Convert internal messages to Ollama chat payload format."""

        return [{"role": msg.role, "content": msg.content} for msg in request.messages]

    def chat(self, request: BackendRequest) -> BackendResponse:
        """Send a non-streaming chat request to Ollama."""

        payload = {
            "model": request.model or self.model,
            "messages": self._messages_payload(request),
            "stream": False,
        }
        response = self.session.post(
            f"{self.endpoint}/api/chat",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        self._status = "ready"

        message = data.get("message", {})
        content = message.get("content", "")
        prompt_eval_count = data.get("prompt_eval_count", 0)
        eval_count = data.get("eval_count", 0)

        return BackendResponse(
            text=content,
            model=data.get("model", payload["model"]),
            provider=self.provider_name,
            usage={
                "prompt_tokens": prompt_eval_count,
                "completion_tokens": eval_count,
            },
            raw=data,
        )

    def stream_chat(self, request: BackendRequest) -> Iterator[StreamingChunk]:
        """Send a streaming chat request to Ollama."""

        payload = {
            "model": request.model or self.model,
            "messages": self._messages_payload(request),
            "stream": True,
        }
        with self.session.post(
            f"{self.endpoint}/api/chat",
            json=payload,
            timeout=self.timeout,
            stream=True,
        ) as response:
            response.raise_for_status()
            self._status = "busy"
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                data = json.loads(raw_line)
                message = data.get("message", {})
                delta = message.get("content", "")
                done = bool(data.get("done", False))
                yield StreamingChunk(
                    delta=delta,
                    done=done,
                    model=data.get("model", payload["model"]),
                    provider=self.provider_name,
                    raw=data,
                )
            self._status = "ready"

    def health_check(self) -> HealthCheckResult:
        """Check if Ollama is reachable and list available models."""

        try:
            response = self.session.get(f"{self.endpoint}/api/tags", timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            models = [item.get("name", "") for item in data.get("models", [])]
            self._status = "ready"
            return HealthCheckResult(
                ok=True,
                status="ready",
                message="Ollama is reachable.",
                provider=self.provider_name,
                details={"models": models, "endpoint": self.endpoint},
            )
        except requests.RequestException as exc:
            self._status = "offline"
            return HealthCheckResult(
                ok=False,
                status="offline",
                message=f"Ollama health check failed: {exc}",
                provider=self.provider_name,
                details={"endpoint": self.endpoint},
            )

    def current_status(self) -> str:
        return self._status
