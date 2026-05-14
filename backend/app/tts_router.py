
from __future__ import annotations
from app.config import load_runtime
from app.tts_noop import NoopTTS

def build_tts_stack():
    cfg = load_runtime().get("tts", {})
    priority = cfg.get("adapter_priority", ["pyttsx3", "noop"])
    stack = []
    for name in priority:
        if name == "pyttsx3":
            try:
                from app.tts_pyttsx3 import Pyttsx3TTS
                stack.append(Pyttsx3TTS())
            except Exception:
                pass
        elif name == "noop":
            stack.append(NoopTTS())
    return stack

def speak_with_fallback(text: str, preferred: str | None = None) -> tuple[str, bool]:
    stack = build_tts_stack()
    if preferred:
        stack = sorted(stack, key=lambda a: 0 if a.name == preferred else 1)
    for adapter in stack:
        try:
            if adapter.available() and adapter.speak(text):
                return adapter.name, True
        except Exception:
            continue
    return "noop", False
