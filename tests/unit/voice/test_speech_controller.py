"""Unit tests for SpeechController — the heart of M2.

Covers, per the brief's DoD:

* ``say()`` cancels the previous utterance and publishes TTSInterrupted.
* ``ptt_down()`` cancels TTS within 100ms.
* Barge-in honours ``voice.modes.barge_in_grace_ms``.
* Live wake → dictation → wake cycle is testable end-to-end against the mock.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable

import pytest
from openmimicry.core.bus import EventBus
from openmimicry.core.contracts import OnChunk
from openmimicry.core.schemas import (
    RuntimeEvent,
    TTSConfig,
    TTSFinished,
    TTSInterrupted,
    UserSpeechFinal,
    UserSpeechStarted,
    WakeDetected,
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
    modes = VoiceModesConfig(
        **{
            **dict(barge_in_enabled=True, barge_in_grace_ms=50),
            **modes_overrides,
        }
    )
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

    assert kinds[0] == "TTSQueued"
    assert "TTSReady" in kinds
    assert "TTSStarted" in kinds
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


async def test_ptt_down_continues_when_audio_cleanup_is_stuck() -> None:
    class StubbornTTS:
        name = "stubborn-tts"

        def __init__(self) -> None:
            self.release_playback = asyncio.Event()
            self.release_stop = asyncio.Event()
            self._is_speaking = False

        async def speak(
            self,
            text_or_stream: str | AsyncIterable[str],
            *,
            config: TTSConfig,
            on_chunk: OnChunk | None = None,
        ) -> None:
            _ = (text_or_stream, config, on_chunk)
            self._is_speaking = True
            try:
                await self.release_playback.wait()
            except asyncio.CancelledError:
                # Model a third-party worker that does not settle when its
                # asyncio wrapper is cancelled.
                await self.release_playback.wait()
                raise
            finally:
                self._is_speaking = False

        async def stop(self) -> None:
            if self._is_speaking:
                await self.release_stop.wait()

        @property
        def is_speaking(self) -> bool:
            return self._is_speaking

        async def healthcheck(self) -> bool:
            return True

    bus = EventBus()
    stt = MockSTTAdapter()
    tts = StubbornTTS()
    ctl = SpeechController(stt=stt, tts=tts, bus=bus, config=_voice_config())
    await ctl.start()
    try:
        await ctl.say("the audio driver never returns")
        await asyncio.sleep(0)
        started = asyncio.get_running_loop().time()

        await asyncio.wait_for(ctl.ptt_down(), timeout=1.0)

        elapsed = asyncio.get_running_loop().time() - started
        assert elapsed < 0.3
        assert ctl.ptt_active is True
    finally:
        tts.release_stop.set()
        tts.release_playback.set()
        await asyncio.sleep(0)
        await asyncio.wait_for(ctl.stop(), timeout=1.0)
        await bus.aclose()


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


async def test_barge_in_is_disabled_by_default_for_speaker_safety() -> None:
    bus = EventBus()
    stt = MockSTTAdapter()
    tts = MockTTSAdapter(chunk_interval_s=0.2)
    ctl = SpeechController(stt=stt, tts=tts, bus=bus, config=VoiceConfig())
    await ctl.start()
    try:
        await ctl.say("do not interrupt the avatar's own voice")
        await asyncio.sleep(0.03)
        await stt.trigger_speech_start()
        await asyncio.sleep(0.12)

        assert tts.is_speaking is True
        assert ctl._current_tts_task is not None
        await ctl._current_tts_task
    finally:
        await ctl.stop()
        await bus.aclose()


async def test_safe_tts_pauses_and_restores_passive_listening() -> None:
    bus = EventBus()
    stt = MockSTTAdapter()
    tts = MockTTSAdapter(chunk_interval_s=0.02)
    config = _voice_config(barge_in_enabled=False)
    ctl = SpeechController(stt=stt, tts=tts, bus=bus, config=config)
    await ctl.start()
    try:
        await ctl.enable_continuous_listening()
        assert stt.start_calls == 1

        await ctl.say("the microphone must not hear this")
        assert ctl.live_listening is False
        assert stt.stop_calls >= 1
        assert ctl._current_tts_task is not None
        await ctl._current_tts_task

        assert ctl.continuous_listening is True
        assert stt.start_calls == 2
    finally:
        await ctl.stop()
        await bus.aclose()


async def test_switching_wake_off_during_tts_cancels_stale_resume() -> None:
    bus = EventBus()
    stt = MockSTTAdapter()
    tts = MockTTSAdapter(chunk_interval_s=0.05)
    config = _voice_config(barge_in_enabled=False)
    ctl = SpeechController(stt=stt, tts=tts, bus=bus, config=config)
    await ctl.start()
    try:
        await ctl.enable_live_listening()
        assert stt.start_calls == 1

        await ctl.say("wake listening must remain off after this speech finishes")
        assert ctl.live_listening is False
        await ctl.disable_live_listening()
        assert ctl._current_tts_task is not None
        await ctl._current_tts_task

        assert ctl.live_listening is False
        assert ctl.listening_mode == "off"
        assert stt.start_calls == 1
    finally:
        await ctl.stop()
        await bus.aclose()


async def test_enable_live_listening_starts_stt_in_wake_mode(controller) -> None:
    ctl, _bus, stt, _tts = controller
    await ctl.enable_live_listening()
    assert ctl.live_listening is True
    assert stt.last_config is not None
    assert stt.last_config.mode == "wake"
    assert stt.last_config.wake_names == ["Mimi"]
    await ctl.disable_live_listening()
    assert ctl.live_listening is False


async def test_wake_listener_ignores_speech_without_name(controller) -> None:
    ctl, bus, stt, _tts = controller
    await ctl.enable_live_listening()
    sub = bus.subscribe()

    await stt.push_transcript("what time is it", is_final=True)
    observed = await asyncio.wait_for(anext(sub), timeout=0.5)
    assert isinstance(observed, UserSpeechFinal)
    assert observed.raw_text == "what time is it"
    assert observed.accepted is False
    assert observed.rejection_reason == "wake_name_missing"


async def test_wake_listener_strips_name_and_publishes_command(controller) -> None:
    ctl, bus, stt, _tts = controller
    await ctl.enable_live_listening()
    sub = bus.subscribe()

    await stt.push_transcript("Mimi, what time is it?", is_final=True)
    first = await asyncio.wait_for(anext(sub), timeout=0.5)
    second = await asyncio.wait_for(anext(sub), timeout=0.5)

    assert isinstance(first, WakeDetected)
    assert first.name == "Mimi"
    assert isinstance(second, UserSpeechFinal)
    assert second.text == "what time is it?"


async def test_wake_alias_recovers_common_mimi_transcription(controller) -> None:
    ctl, bus, stt, _tts = controller
    await ctl.enable_live_listening()
    sub = bus.subscribe()

    await stt.push_transcript("Me me, tell me a joke", is_final=True)
    await asyncio.wait_for(anext(sub), timeout=0.5)  # WakeDetected
    final = await asyncio.wait_for(anext(sub), timeout=0.5)

    assert isinstance(final, UserSpeechFinal)
    assert final.accepted is True
    assert final.text == "tell me a joke"


async def test_duplicate_wake_final_is_visible_but_not_accepted(controller) -> None:
    ctl, bus, stt, _tts = controller
    await ctl.enable_live_listening()
    sub = bus.subscribe()

    await stt.push_transcript("Mimi, tell me a joke", is_final=True)
    await asyncio.wait_for(anext(sub), timeout=0.5)
    first = await asyncio.wait_for(anext(sub), timeout=0.5)
    await stt.push_transcript("Mimi, tell me a joke", is_final=True)
    await asyncio.wait_for(anext(sub), timeout=0.5)
    duplicate = await asyncio.wait_for(anext(sub), timeout=0.5)

    assert isinstance(first, UserSpeechFinal) and first.accepted is True
    assert isinstance(duplicate, UserSpeechFinal) and duplicate.accepted is False
    assert duplicate.rejection_reason == "duplicate"


async def test_updating_wake_name_restarts_active_listener(controller) -> None:
    ctl, bus, stt, _tts = controller
    await ctl.enable_live_listening()
    starts_before = stt.start_calls
    await ctl.set_wake_names(["Octo", "Hey Octo", "octo"])

    assert ctl.wake_names == ["Hey Octo", "Octo"]
    assert stt.start_calls == starts_before + 1
    sub = bus.subscribe()
    await stt.push_transcript("Octo: say hello", is_final=True)
    await asyncio.wait_for(anext(sub), timeout=0.5)
    final = await asyncio.wait_for(anext(sub), timeout=0.5)
    assert isinstance(final, UserSpeechFinal)
    assert final.text == "say hello"


async def test_enable_continuous_listening_uses_plain_dictation(controller) -> None:
    ctl, _bus, stt, _tts = controller
    await ctl.enable_continuous_listening()
    assert ctl.continuous_listening is True
    assert ctl.listening_mode == "continuous"
    assert stt.last_config is not None
    assert stt.last_config.mode == "continuous"
    assert stt.last_config.wake_names == []
    await ctl.disable_live_listening()


async def test_updating_speech_pause_restarts_active_listener(controller) -> None:
    ctl, _bus, stt, _tts = controller
    await ctl.enable_continuous_listening()
    starts_before = stt.start_calls

    await ctl.set_post_speech_silence_duration(1.5)

    assert ctl.post_speech_silence_duration == 1.5
    assert stt.start_calls == starts_before + 1
    assert stt.last_config is not None
    assert stt.last_config.post_speech_silence_duration == 1.5
    await ctl.disable_live_listening()


async def test_ptt_temporarily_pauses_and_restores_continuous_listening(controller) -> None:
    ctl, bus, stt, _tts = controller
    await ctl.enable_continuous_listening()
    assert ctl.continuous_listening is True

    sub = bus.subscribe()

    async def wait_for_final() -> UserSpeechFinal:
        async for event in sub:
            if isinstance(event, UserSpeechFinal):
                return event
        raise AssertionError("event bus closed before speech final")

    final_task = asyncio.create_task(wait_for_final())
    await ctl.ptt_down()
    assert ctl.ptt_active is True
    assert ctl.listening_mode == "push_to_talk"
    await stt.push_transcript("toolbar push to talk", is_final=True)
    await ctl.ptt_up()

    final = await asyncio.wait_for(final_task, timeout=1.0)
    assert final.text == "toolbar push to talk"
    assert ctl.ptt_active is False
    assert ctl.continuous_listening is True
    assert ctl.listening_mode == "continuous"
