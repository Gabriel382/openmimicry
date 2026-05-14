
from __future__ import annotations
from app.tts_base import BaseTTS

class NoopTTS(BaseTTS):
    name = "noop"

    def available(self) -> bool:
        return True

    def speak(self, text: str) -> bool:
        return False
