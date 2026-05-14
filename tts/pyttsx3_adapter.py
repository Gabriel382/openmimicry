
"""Local free TTS adapter using pyttsx3, based on the uploaded example."""

from __future__ import annotations

import threading
import time
import pyttsx3

from tts.base import BaseTTSAdapter


class Pyttsx3Adapter(BaseTTSAdapter):
    """Simple synchronous TTS wrapper with speaking state tracking."""

    def __init__(self, rate: int = 175, volume: float = 1.0) -> None:
        """Initialize pyttsx3 and configure basic voice properties."""
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", rate)
        self.engine.setProperty("volume", volume)
        self._speaking = False
        self._lock = threading.Lock()

    def speak(self, text: str) -> None:
        """Speak the provided text synchronously."""
        if not text.strip():
            return

        with self._lock:
            self._speaking = True

        try:
            self.engine.say(text)
            self.engine.runAndWait()
        finally:
            with self._lock:
                self._speaking = False

    def speak_async(self, text: str) -> threading.Thread:
        """Speak asynchronously on a background thread."""
        thread = threading.Thread(target=self.speak, args=(text,), daemon=True)
        thread.start()
        return thread

    def is_speaking(self) -> bool:
        """Return whether TTS is currently speaking."""
        with self._lock:
            return self._speaking

    def stop(self) -> None:
        """Stop current speech if supported."""
        try:
            self.engine.stop()
        finally:
            with self._lock:
                self._speaking = False
