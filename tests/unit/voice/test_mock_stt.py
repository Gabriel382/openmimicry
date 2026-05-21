"""Unit tests for MockSTTAdapter."""

from __future__ import annotations

import asyncio

from openmimicry.core.contracts import STTAdapter
from openmimicry.core.schemas import STTConfig
from openmimicry.voice.mocks import MockSTTAdapter


def test_mock_satisfies_stt_protocol() -> None:
    assert isinstance(MockSTTAdapter(), STTAdapter)


async def test_start_records_config_and_increments_counter() -> None:
    stt = MockSTTAdapter()
    cfg = STTConfig(mode="dictation")
    await stt.start(cfg)
    assert stt.last_config == cfg
    assert stt.start_calls == 1


async def test_push_transcript_streams_to_consumer() -> None:
    stt = MockSTTAdapter()
    await stt.start(STTConfig())

    received = []

    async def consume() -> None:
        async for t in stt.transcripts:
            received.append((t.text, t.is_final))
            if len(received) == 3:
                return

    task = asyncio.create_task(consume())
    await stt.push_transcript("a", is_final=False)
    await stt.push_transcript("b", is_final=False)
    await stt.push_transcript("hello", is_final=True)
    await asyncio.wait_for(task, timeout=0.5)

    assert received == [("a", False), ("b", False), ("hello", True)]
    await stt.stop()


async def test_stop_drains_iterator_with_sentinel() -> None:
    stt = MockSTTAdapter()
    await stt.start(STTConfig())

    items = []

    async def consume() -> None:
        async for t in stt.transcripts:
            items.append(t.text)

    task = asyncio.create_task(consume())
    await stt.push_transcript("only", is_final=True)
    await stt.stop()
    await asyncio.wait_for(task, timeout=0.5)
    assert items == ["only"]


async def test_vad_toggle_helpers() -> None:
    stt = MockSTTAdapter()
    assert stt.vad_active is False
    await stt.trigger_speech_start()
    assert stt.vad_active is True
    await stt.trigger_speech_end()
    assert stt.vad_active is False


async def test_healthcheck_returns_bool() -> None:
    stt = MockSTTAdapter()
    assert isinstance(await stt.healthcheck(), bool)
    assert await stt.healthcheck() is True
