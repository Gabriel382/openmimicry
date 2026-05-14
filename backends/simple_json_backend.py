
"""Minimal backend bridge for the animated demo.

It can either:
- call a local Ollama endpoint directly
- or use a mock local reply when Ollama is unavailable
"""

from __future__ import annotations

from dataclasses import dataclass
import requests


@dataclass(slots=True)
class SimpleBackendConfig:
    """Minimal runtime backend config."""

    provider: str = "ollama"
    endpoint: str = "http://localhost:11434"
    model: str = "qwen2.5:1.5b-instruct-q4_K_M"
    fallback_to_mock: bool = True


class SimpleJSONBackend:
    """Very small backend used by the 6.5 demo."""

    def __init__(self, config: SimpleBackendConfig) -> None:
        """Store runtime config."""
        self.config = config

    def ask(self, prompt: str) -> tuple[str, str]:
        """Return (backend_name, text_response)."""
        if self.config.provider == "ollama":
            try:
                payload = {
                    "model": self.config.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                }
                response = requests.post(
                    f"{self.config.endpoint}/api/chat",
                    json=payload,
                    timeout=120,
                )
                response.raise_for_status()
                data = response.json()
                text = data.get("message", {}).get("content", "").strip()
                if not text:
                    text = "I did not receive any content from the model."
                return "ollama", text
            except Exception as exc:
                if not self.config.fallback_to_mock:
                    raise
                return "mock", f"I could not reach the real model, so I am using a fallback. Details: {exc}"

        return "mock", self._mock_reply(prompt)

    @staticmethod
    def _mock_reply(prompt: str) -> str:
        """Generate a tiny local mock reply."""
        text = prompt.strip()
        if not text:
            return "Please ask me something."
        return f"Mock response to: {text}"
