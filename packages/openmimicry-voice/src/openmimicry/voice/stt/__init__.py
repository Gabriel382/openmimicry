"""STT adapters."""

from __future__ import annotations

from .base import STTAdapter
from .realtimestt_adapter import RealtimeSTTAdapter, RealtimeSTTSettings

__all__ = ["RealtimeSTTAdapter", "RealtimeSTTSettings", "STTAdapter"]
