"""Voice Protocols — STT, TTS, SpeechController, WakeController.

Source of truth: ``docs/contracts.md`` §4.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator, Callable
from typing import Protocol, runtime_checkable

from ..schemas.voice import STTConfig, Transcript, TTSChunkBoundary, TTSConfig

__all__ = [
    "OnChunk",
    "STTAdapter",
    "SpeechController",
    "TTSAdapter",
    "WakeController",
]


OnChunk = Callable[[TTSChunkBoundary], None]
"""Callback shape for ``TTSAdapter.speak``'s ``on_chunk`` argument."""


@runtime_checkable
class STTAdapter(Protocol):
    """Speech-to-text adapter."""

    name: str

    async def start(self, config: STTConfig) -> None: ...
    async def stop(self) -> None: ...

    @property
    def transcripts(self) -> AsyncIterator[Transcript]:
        """An async iterator of ``Transcript`` updates, partial + final."""
        ...

    @property
    def vad_active(self) -> bool:
        """True when the VAD currently believes the user is speaking."""
        ...

    async def healthcheck(self) -> bool: ...


@runtime_checkable
class TTSAdapter(Protocol):
    """Text-to-speech adapter with cooperative interruption."""

    name: str

    async def speak(
        self,
        text_or_stream: str | AsyncIterable[str],
        *,
        config: TTSConfig,
        on_chunk: OnChunk | None = None,
    ) -> None: ...

    async def stop(self) -> None: ...

    @property
    def is_speaking(self) -> bool: ...

    async def healthcheck(self) -> bool: ...


class SpeechController(Protocol):
    """Higher-level orchestration: PTT, live wake, barge-in, say()."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def say(self, text_or_stream: str | AsyncIterable[str]) -> None: ...
    async def interrupt(self) -> None: ...
    async def ptt_down(self) -> None: ...
    async def ptt_up(self) -> None: ...
    async def enable_live_listening(self, *, wake_names: list[str] | None) -> None: ...
    async def disable_live_listening(self) -> None: ...


class WakeController(Protocol):
    """Toggle for the wake-name listening path."""

    async def enable(self) -> None: ...
    async def disable(self) -> None: ...
