"""Unit tests for MockTTSAdapter."""

from __future__ import annotations

import asyncio

import pytest
from openmimicry.core.contracts import TTSAdapter
from openmimicry.core.schemas import TTSConfig
from openmimicry.voice.mocks import MockTTSAdapter


def test_mock_satisfies_tts_protocol() -> None:
    assert isinstance(MockTTSAdapter(), TTSAdapter)


async def test_speak_records_string() -> None:
    tts = MockTTSAdapter(chunk_interval_s=0.0)
    await tts.speak("hello world", config=TTSConfig())
    assert tts.spoken == ["hello world"]
    assert tts.last_config is not None
    assert tts.is_speaking is False


async def test_speak_records_stream() -> None:
    tts = MockTTSAdapter(chunk_interval_s=0.0)

    async def gen():
        yield "a"
        yield "b"
        yield "c"

    await tts.speak(gen(), config=TTSConfig())
    assert tts.spoken == ["abc"]


async def test_stop_cancels_speak_within_100ms() -> None:
    """PTT-down must cancel TTS within 100ms (M2 DoD)."""
    tts = MockTTSAdapter(chunk_interval_s=0.05)

    speak_task = asyncio.create_task(
        tts.speak("a very long " * 100, config=TTSConfig())
    )
    await asyncio.sleep(0.02)
    assert tts.is_speaking is True

    start = asyncio.get_event_loop().time()
    await tts.stop()
    try:
        await asyncio.wait_for(speak_task, timeout=0.5)
    except asyncio.CancelledError:
        pass
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 0.1, f"stop() took {elapsed:.3f}s, must be <100ms"
    assert tts.interrupt_calls == 1
    assert tts.is_speaking is False


async def test_healthcheck_returns_bool() -> None:
    assert isinstance(await MockTTSAdapter().healthcheck(), bool)
