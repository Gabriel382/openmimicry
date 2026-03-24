
from __future__ import annotations
from app.tts.base import BaseTTSAdapter

class Pyttsx3Adapter(BaseTTSAdapter):
    name = "pyttsx3"

    def __init__(self, rate: int = 175, volume: float = 1.0):
        import pyttsx3
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", rate)
        self.engine.setProperty("volume", volume)

    def available(self) -> bool:
        return True

    def speak(self, text: str) -> bool:
        if not text.strip():
            return False
        self.engine.say(text)
        self.engine.runAndWait()
        return True
