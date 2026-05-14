
"""Avatar state definitions for OpenMimicry."""

from __future__ import annotations
from enum import Enum


class AvatarState(str, Enum):
    """Supported high-level avatar states."""

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    HAPPY = "happy"
    ERROR = "error"

    @classmethod
    def values(cls) -> list[str]:
        """Return all state names as strings."""
        return [state.value for state in cls]
