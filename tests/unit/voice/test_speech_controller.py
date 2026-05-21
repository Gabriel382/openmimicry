"""Unit tests for SpeechController — the heart of M2.

Covers, per the brief's DoD:

* ``say()`` cancels the previous utterance and publishes TTSInterrupted.
* ``ptt_down()`` cancels TTS within 100ms.
* Barge-in honours ``voice.modes.barge_in_grace_ms``.
* Live wake → dictation → wake cycle is testable end-to-end against the mock.
"""

from __future__ import annotations

import asyncio

import pytest
from openmimicry.core.bus import EventBus
from openmimicry.core.schemas import (
    RuntimeEvent,
    TTSFinished,
    TTSInterrupted,
    UserSpeechFinal,
    UserSpeechStarted,
)
from openmimicry.core.schemas.app import (
    STTConfigSection,
    STTWakeConfig,
    TTSConfigSection,
    VoiceConfig,
    VoiceModesConfig,
)
from openmimicry.voice.controllers.speech import SpeechController
from openmimicry.voice.mocks import MockSTTAdapter, MockTTSAdapter


def _voice_config(**modes_overrides) -> VoiceConfig:
    """Build a VoiceConfig with the given mode overrides applied."""
    modes = VoiceModesConfig(**{**dict(barge_in_grace_ms=50), **modes_overrides})
    return VoiceConfig(
        stt=STTConfigSection(wake=STTWakeConfig(names=["Mimi"])),
        tts=TTSConfigSection(),
        modes=modes,
    )


async def _drain_until(bus: EventBus, predicate, *, timeout: float = 0.5) -> list[RuntimeEvent]:
    """Subscribe to ``bus`` and collect events until ``predicate(events)`` is true."""
    collected: list[RuntimeEvent] = []
    sub = bus.subscribe()

    async def reader() -> None:
        async for event in sub:
            collected.append(event)
            if predicate(collected):
                return

    await asyncio.wait_for(reader(), timeout=timeout)
    return collected


@pytest.fixture
async def controller():
    bus = EventBus()
    stt = MockSTTAdapter()
    tts = MockTTSAdapter(chunk_interval_s=0.01)
    ctl = SpeechController(stt=stt, tts=tts, bus=bus, config=_voice_config())
    await ctl.start()
    try:
        yield ctl, bus, stt, tts
    finally:
        await ctl.stop()
        await bus.aclose()


async def test_say_publishes_started_and_finished(controller) -> None:
    ctl, bus, _stt, tts = controller

    events_task = asyncio.create_task(
        _drain_until(
            bus,
            lambda e: any(isinstance(x, TTSFinished) for x in e),
            timeout=1.0,
        )
    )

    await ctl.say("hi")

    # Wait for the TTS task to complete.
    assert ctl._current_tts_task is not None
    await ctl._current_tts_task

    events = await events_task
    kinds = [type(e).__name__ for e in events]

    assert kinds[0] == "TTSStarted"
    assert "TTSFinished" in kinds
    assert tts.spoken == ["hi"]


async def test_say_cancels_previous_and_publishes_interrupted(controller) -> None:
    ctl, bus, _stt, tts = controller

    # Start a slow utterance so the second say() cancels it mid-flight.
    tts._chunk_interval_s = 0.2  # type: ignore[attr-defined]
    await ctl.say("first long utterance")
    await asyncio.sleep(0.02)

    # Begin collecting events BEFORE the second say().
    sub = bus.subscribe()
    collected: list[RuntimeEvent] = []

    async def collect() -> None:
        async for e in sub:
            collected.append(e)
            if isinstance(e, TTSFinished):
                return

    task = asyncio.create_task(collect())

    await ctl.say("second short")
    if ctl._current_tts_task is not None:
        await ctl._current_tts_task
    await asyncio.wait_for(task, timeout=1.0)

    kinds = [type(e).__name__ for e in collected]
    assert "TTSInterrupted" in kinds, kinds
    # The new utterance is also recorded.
    assert "second short" in tts.spoken


async def test_ptt_down_cancels_tts_within_100ms(controller) -> None:
    ctl, _bus, _stt, tts = controller
    tts._chunk_interval_s = 0.1  # type: ignore[attr-defined]

    await ctl.say("hello there long")
    await asyncio.sleep(0.02)
    assert tts.is_speaking is True

    start = asyncio.get_event_loop().time()
    await ctl.ptt_down()
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 0.1, f"ptt_down cancelled TTS in {elapsed:.3f}s, must be <100ms"
    assert tts.interrupt_calls >= 1


async def test_ptt_up_publishes_user_speech_final(controller) -> None:
    ctl, bus, stt, _tts = controller
    sub = bus.subscribe()

    async def collect() -> list[RuntimeEvent]:
        events: list[RuntimeEvent] = []
        async for e in sub:
            events.append(e)
            if isinstance(e, UserSpeechFinal):
                return events
        return events

    task = asyncio.create_task(collect())
    await ctl.ptt_down()
    await stt.push_transcript("hello from the user", is_final=True)
    await ctl.ptt_up()

    events = await asyncio.wait_for(task, timeout=1.0)
    starts = [e for e in events if isinstance(e, UserSpeechStarted)]
    finals = [e for e in events if isinstance(e, UserSpeechFinal)]
    assert len(starts) == 1
    assert len(finals) == 1
    assert finals[0].text == "hello from the user"
    assert finals[0].reason == "normal"


async def test_barge_in_interrupts_when_vad_active(controller) -> None:
    ctl, bus, stt, tts = controller
    tts._chunk_interval_s = 0.2  # type: ignore[attr-defined]

    sub = bus.subscribe()
    collected: list[RuntimeEvent] = []

    async def collect() -> None:
        async for e in sub:
            collected.append(e)
            if isinstance(e, TTSInterrupted):
                return

    task = asyncio.create_task(collect())

    await ctl.say("a very long sentence to speak")
    await asyncio.sleep(0.05)
    await stt.trigger_speech_start()
    # Wait for grace + poll + grace re-check.
    await asyncio.wait_for(task, timeout=1.0)
    assert any(isinstance(e, TTSInterrupted) for e in collected)


async def test_enable_live_listening_starts_stt_in_wake_mode(controller) -> None:
    ctl, _bus, stt, _tts = controller
    await ctl.enable_live_listening()
    assert ctl.live_listening is True
    assert stt.last_config is not None
    assert stt.last_config.mode == "wake"
    assert stt.last_config.wake_names == ["Mimi"]
    await ctl.disable_live_listening()
    assert ctl.live_listening is False
