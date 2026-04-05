
from __future__ import annotations
from app.llm_base import BaseLLM

class MockLLM(BaseLLM):
    name = "mock"

    def health(self) -> tuple[bool, str]:
        return True, "Mock ready."

    def chat(self, text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return "Please ask me something."
        if "error" in cleaned.lower():
            return "I detected an error-like request. Let's handle it carefully."
        if any(word in cleaned.lower() for word in ["hello", "good", "great"]):
            return "Hello! How can I assist you today?"
        return f"Mock reply: {cleaned}"
