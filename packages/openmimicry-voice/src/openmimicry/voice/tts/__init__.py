"""TTS adapters."""

from __future__ import annotations

from .base import TTSAdapter
from .realtimetts_adapter import RealtimeTTSAdapter, RealtimeTTSSettings

__all__ = ["RealtimeTTSAdapter", "RealtimeTTSSettings", "TTSAdapter"]
