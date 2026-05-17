"""Programmable mock STT and TTS adapters — the canonical fixtures.

Every consumer (SpeechController unit tests, M6 backend integration tests,
M3 director tests) drives these mocks instead of touching a real audio
stack. Both satisfy the frozen STTAdapter / TTSAdapter Protocols and expose
test-only helpers (``push_transcript``, ``trigger_speech_*``, ``spoken``,
``interrupt_calls``) so tests can assert on observed behaviour without
inspecting private state.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any

from openmimicry.core.contracts import OnChunk
from openmimicry.core.schemas import STTConfig, Transcript, TTSConfig

__all__ = [
    "MockSTTAdapter",
    "MockTTSAdapter",
    "make_mock_stt_adapter",
    "make_mock_tts_adapter",
]


class MockSTTAdapter:
    """Programmable STTAdapter.

    Drive the async transcript stream via :meth:`push_transcript`. Toggle
    ``vad_active`` via :meth:`trigger_speech_start` / ``_end`` so
    SpeechController barge-in logic can be exercised without an audio
    device.
    """

    name: str = "mock-stt"

    def __init__(self) -> None:
        self._queue: asyncio.Queue[Transcript | None] = asyncio.Queue()
        self._vad_active: bool = False
        self._started: bool = False
        self._closed: bool = False
        self.last_config: STTConfig | None = None
        self.start_calls: int = 0
        self.stop_calls: int = 0

    async def start(self, config: STTConfig) -> None:
        self.last_config = config
        self.start_calls += 1
        self._started = True
        self._closed = False

    async def stop(self) -> None:
        self.stop_calls += 1
        self._started = False
        self._vad_active = False
        # Sentinel so any pending iterator exits cleanly.
        await self._queue.put(None)

    @property
    def transcripts(self) -> AsyncIterator[Transcript]:
        return self._iter_transcripts()

    async def _iter_transcripts(self) -> AsyncIterator[Transcript]:
        while True:
            item = await self._queue.get()
            if item is None:
                return
            yield item

    @property
    def vad_active(self) -> bool:
        return self._vad_active

    async def healthcheck(self) -> bool:
        return not self._closed

    # ---------------------------------------------------------- test helpers

    async def push_transcript(self, text: str, *, is_final: bool = True) -> None:
        """Queue a Transcript onto the async stream."""
        await self._queue.put(Transcript(text=text, is_final=is_final))

    async def trigger_speech_start(self) -> None:
        self._vad_active = True

    async def trigger_speech_end(self) -> None:
        self._vad_active = False


class MockTTSAdapter:
    """Recording TTSAdapter.

    ``speak()`` records every text and sleeps ``chunk_interval_s`` per
    logical chunk, honouring a cooperative cancel flag flipped by
    ``stop()``. Tests assert on ``spoken`` and ``interrupt_calls``.
    """

    name: str = "mock-tts"

    def __init__(self, *, chunk_interval_s: float = 0.01) -> None:
        self._chunk_interval_s = chunk_interval_s
        self._cancel = asyncio.Event()
        self._is_speaking: bool = False
        self._closed: bool = False
        self.spoken: list[str] = []
        self.interrupt_calls: int = 0
        self.last_config: TTSConfig | None = None
        self.last_on_chunk: OnChunk | None = None

    async def speak(
        self,
        text_or_stream: str | AsyncIterable[str],
        *,
        config: TTSConfig,
        on_chunk: OnChunk | None = None,
    ) -> None:
        self.last_config = config
        self.last_on_chunk = on_chunk
        self._cancel.clear()
        self._is_speaking = True
        try:
            if isinstance(text_or_stream, str):
                pieces: list[str] = [text_or_stream]
            else:
                pieces = []
                async for piece in text_or_stream:
                    if self._cancel.is_set():
                        break
                    pieces.append(piece)
            self.spoken.append("".join(pieces))

            # Simulate streaming; honour cooperative cancel between chunks.
            for _ in pieces or [""]:
                if self._cancel.is_set():
                    return
                await asyncio.sleep(self._chunk_interval_s)
        finally:
            self._is_speaking = False

    async def stop(self) -> None:
        self.interrupt_calls += 1
        self._cancel.set()
        # Yield once so any in-flight speak() observes the flag.
        await asyncio.sleep(0)

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    async def healthcheck(self) -> bool:
        return not self._closed


def make_mock_stt_adapter(*_args: Any, **_kwargs: Any) -> MockSTTAdapter:
    """Factory used by the contract conftest."""
    return MockSTTAdapter()


def make_mock_tts_adapter(*_args: Any, **_kwargs: Any) -> MockTTSAdapter:
    """Factory used by the contract conftest."""
    return MockTTSAdapter()
