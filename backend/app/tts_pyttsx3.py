
from __future__ import annotations
from app.tts_base import BaseTTS

class Pyttsx3TTS(BaseTTS):
    name = "pyttsx3"

    def __init__(self):
        import pyttsx3
        self.engine = pyttsx3.init()

    def available(self) -> bool:
        return True

    def speak(self, text: str) -> bool:
        if not text.strip():
            return False
        self.engine.say(text)
        self.engine.runAndWait()
        return True
