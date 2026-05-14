
from __future__ import annotations
from app.tts.base import BaseTTSAdapter

class NoopTTSAdapter(BaseTTSAdapter):
    name = "noop"

    def available(self) -> bool:
        return True

    def speak(self, text: str) -> bool:
        return False
