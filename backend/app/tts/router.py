
from __future__ import annotations
from app.config import load_runtime
from app.tts.noop import NoopTTSAdapter
from app.tts.piper_adapter import PiperAdapter

def build_stack():
    cfg = load_runtime().get("tts", {})
    priority = cfg.get("adapter_priority", ["piper", "pyttsx3", "noop"])
    stack = []
    for name in priority:
        if name == "piper":
            stack.append(PiperAdapter(
                executable=cfg.get("piper", {}).get("executable", "piper"),
                model_path=cfg.get("piper", {}).get("model_path", ""),
            ))
        elif name == "pyttsx3":
            try:
                from app.tts.pyttsx3_adapter import Pyttsx3Adapter
                stack.append(Pyttsx3Adapter(
                    rate=cfg.get("pyttsx3", {}).get("rate", 175),
                    volume=cfg.get("pyttsx3", {}).get("volume", 1.0),
                ))
            except Exception:
                pass
        elif name == "noop":
            stack.append(NoopTTSAdapter())
    return stack

def speak_with_fallback(text: str, preferred: str | None = None) -> tuple[str, bool]:
    stack = build_stack()
    if preferred:
        stack = sorted(stack, key=lambda a: 0 if a.name == preferred else 1)
    for adapter in stack:
        try:
            if adapter.available() and adapter.speak(text):
                return adapter.name, True
        except Exception:
            continue
    return "noop", False
