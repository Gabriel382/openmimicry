"""STT adapters."""

from __future__ import annotations

from .base import STTAdapter
from .isolated_faster_whisper import (
    IsolatedFasterWhisperAdapter,
    IsolatedFasterWhisperSettings,
    IsolatedSTTUnavailable,
)
from .realtimestt_adapter import RealtimeSTTAdapter, RealtimeSTTSettings

__all__ = [
    "IsolatedFasterWhisperAdapter",
    "IsolatedFasterWhisperSettings",
    "IsolatedSTTUnavailable",
    "RealtimeSTTAdapter",
    "RealtimeSTTSettings",
    "STTAdapter",
]
