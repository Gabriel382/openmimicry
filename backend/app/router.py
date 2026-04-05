
from __future__ import annotations
from app.config import load_runtime
from app.llm_mock import MockLLM
from app.llm_ollama import OllamaLLM

def build_llm():
    cfg = load_runtime().get("backend", {})
    if cfg.get("provider") == "ollama":
        return OllamaLLM(
            cfg.get("endpoint", "http://localhost:11434"),
            cfg.get("model", "qwen2.5:1.5b-instruct-q4_K_M"),
        )
    return MockLLM()

def ask(text: str) -> tuple[str, str]:
    llm = build_llm()
    ok, _ = llm.health()
    if ok:
        try:
            return llm.name, llm.chat(text)
        except Exception:
            pass
    mock = MockLLM()
    return mock.name, mock.chat(text)
