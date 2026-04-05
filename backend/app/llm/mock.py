
from __future__ import annotations
from app.llm.base import BaseLLMAdapter

class MockLLMAdapter(BaseLLMAdapter):
    name = "mock"

    def health(self) -> tuple[bool, str]:
        return True, "Mock backend is ready."

    def chat(self, text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return "Please ask me something."
        if "error" in cleaned.lower():
            return "I detected an error-like request. Let's handle it carefully."
        if "happy" in cleaned.lower():
            return "Great news, this sounds good."
        return f"Mock reply: {cleaned}"
