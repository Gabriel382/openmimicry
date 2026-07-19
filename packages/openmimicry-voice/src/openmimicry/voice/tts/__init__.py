"""TTS adapters."""

from __future__ import annotations

from .base import TTSAdapter
from .chatterbox import ChatterboxSettings, ChatterboxTTSAdapter
from .elevenlabs import ElevenLabsSettings, ElevenLabsTTSAdapter
from .isolated_piper import (
    IsolatedPiperSettings,
    IsolatedPiperTTSAdapter,
    IsolatedTTSUnavailable,
)
from .realtimetts_adapter import RealtimeTTSAdapter, RealtimeTTSSettings
from .system_command import SystemCommandTTSAdapter, SystemTTSUnavailable

__all__ = [
    "ChatterboxSettings",
    "ChatterboxTTSAdapter",
    "ElevenLabsSettings",
    "ElevenLabsTTSAdapter",
    "IsolatedPiperSettings",
    "IsolatedPiperTTSAdapter",
    "IsolatedTTSUnavailable",
    "RealtimeTTSAdapter",
    "RealtimeTTSSettings",
    "SystemCommandTTSAdapter",
    "SystemTTSUnavailable",
    "TTSAdapter",
]
