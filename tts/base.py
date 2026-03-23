
"""Base TTS adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseTTSAdapter(ABC):
    """Abstract TTS adapter used by the animated 2D runtime."""

    @abstractmethod
    def speak(self, text: str) -> None:
        """Speak text synchronously."""

    @abstractmethod
    def is_speaking(self) -> bool:
        """Return whether the engine is currently speaking."""

    @abstractmethod
    def stop(self) -> None:
        """Stop current speech."""
