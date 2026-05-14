
from __future__ import annotations
import requests
from app.llm_base import BaseLLM

class OllamaLLM(BaseLLM):
    name = "ollama"

    def __init__(self, endpoint: str, model: str):
        self.endpoint = endpoint.rstrip("/")
        self.model = model

    def health(self) -> tuple[bool, str]:
        try:
            r = requests.get(f"{self.endpoint}/api/tags", timeout=10)
            r.raise_for_status()
            return True, "Ollama reachable."
        except Exception as exc:
            return False, f"Ollama unavailable: {exc}"

    def chat(self, text: str) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": text}],
            "stream": False,
        }
        r = requests.post(f"{self.endpoint}/api/chat", json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        return data.get("message", {}).get("content", "").strip() or "No content returned."
