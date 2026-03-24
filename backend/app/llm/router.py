
from __future__ import annotations
from app.config import load_runtime
from app.llm.mock import MockLLMAdapter
from app.llm.ollama import OllamaAdapter

def build_llm():
    cfg = load_runtime().get("backend", {})
    if cfg.get("provider") == "ollama":
        return OllamaAdapter(
            endpoint=cfg.get("endpoint", "http://localhost:11434"),
            model=cfg.get("model", "qwen2.5:1.5b-instruct-q4_K_M"),
        )
    return MockLLMAdapter()

def ask_with_fallback(text: str) -> tuple[str, str]:
    llm = build_llm()
    ok, _ = llm.health()
    if ok:
        try:
            return llm.name, llm.chat(text)
        except Exception:
            pass
    mock = MockLLMAdapter()
    return mock.name, mock.chat(text)
