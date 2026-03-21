"""Avatar state model used by the simple 2D runtime."""

from __future__ import annotations

from enum import Enum


class AvatarState(str, Enum):
    """Canonical states supported by the first 2D avatar runtime."""

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    HAPPY = "happy"
    ERROR = "error"

    @classmethod
    def default(cls) -> "AvatarState":
        """Return the default avatar state."""
        return cls.IDLE
