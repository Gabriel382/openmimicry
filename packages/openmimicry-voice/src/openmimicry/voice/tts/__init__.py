"""TTS adapters."""

from __future__ import annotations

from .base import TTSAdapter
from .isolated_piper import (
    IsolatedPiperSettings,
    IsolatedPiperTTSAdapter,
    IsolatedTTSUnavailable,
)
from .realtimetts_adapter import RealtimeTTSAdapter, RealtimeTTSSettings

__all__ = [
    "IsolatedPiperSettings",
    "IsolatedPiperTTSAdapter",
    "IsolatedTTSUnavailable",
    "RealtimeTTSAdapter",
    "RealtimeTTSSettings",
    "TTSAdapter",
]
