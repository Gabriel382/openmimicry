"""Unit tests for RealtimeSTTAdapter.

RealtimeSTT is not a test dependency. We inject a fake ``RealtimeSTT``
module via ``sys.modules`` so the adapter's lazy import resolves to our
scriptable fake.
"""

from __future__ import annotations

import asyncio
import sys
import types

import pytest
from openmimicry.core.schemas import STTConfig
from openmimicry.voice.stt.realtimestt_adapter import (
    RealtimeSTTAdapter,
    RealtimeSTTUnavailable,
)


class _FakeRecorder:
    """Stand-in for ``AudioToTextRecorder``.

    Tests poke ``self._on_partial`` and ``self._finals`` to drive output.
    ``text()`` returns the next queued final or "" to signal end-of-stream.
    """

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self._on_partial = kwargs.get("on_realtime_transcription_update")
        self._on_start = kwargs.get("on_recording_start")
        self._on_stop = kwargs.get("on_recording_stop")
        self._finals: list[str] = []
        self._stopped = False

    def queue_final(self, text: str) -> None:
        self._finals.append(text)

    def text(self) -> str:
        if self._stopped:
            return ""
        if self._finals:
            return self._finals.pop(0)
        return ""

    def stop(self) -> None:
        self._stopped = True

    def abort(self) -> None:
        # Pausing a listening session must not destroy the warm recorder.
        pass

    def shutdown(self) -> None:
        self._stopped = True


def _install_fake_realtimestt(monkeypatch: pytest.MonkeyPatch, recorder: _FakeRecorder):
    """Inject a fake ``RealtimeSTT`` module."""

    captured: dict = {}

    def factory(**kwargs):
        captured["calls"] = captured.get("calls", 0) + 1
        captured["kwargs"] = kwargs
        # Re-bind the recorder's callbacks to those provided in this call.
        recorder.__init__(**kwargs)  # type: ignore[misc]
        return recorder

    fake = types.SimpleNamespace(AudioToTextRecorder=factory)
    monkeypatch.setitem(sys.modules, "RealtimeSTT", fake)
    return captured


async def test_unavailable_when_realtimestt_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "RealtimeSTT", raising=False)
    monkeypatch.setattr(
        "openmimicry.voice.stt.realtimestt_adapter._import_recorder_class",
        lambda: (_ for _ in ()).throw(RealtimeSTTUnavailable("not installed")),
    )
    adapter = RealtimeSTTAdapter()
    assert await adapter.healthcheck() is False
    with pytest.raises(RealtimeSTTUnavailable):
        await adapter.start(STTConfig())


async def test_partial_transcript_callback_streams(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _FakeRecorder()
    captured = _install_fake_realtimestt(monkeypatch, recorder)

    adapter = RealtimeSTTAdapter()
    await adapter.start(STTConfig(mode="dictation", language="en"))
    assert "on_realtime_transcription_update" in captured["kwargs"]

    received = []

    async def consume():
        async for t in adapter.transcripts:
            received.append((t.text, t.is_final))
            return

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)
    # Simulate RealtimeSTT's worker thread firing the partial callback.
    recorder._on_partial("partial-a")
    recorder._on_partial("partial-b")
    await asyncio.wait_for(task, timeout=0.5)

    # Realtime previews are deliberately coalesced: the UI needs the newest
    # hypothesis, not an ever-growing backlog that delays the final result.
    recorder._on_partial("partial-c")
    next_preview = await asyncio.wait_for(anext(adapter.transcripts), timeout=0.5)

    await adapter.stop()
    assert received == [("partial-b", False)]
    assert (next_preview.text, next_preview.is_final) == ("partial-c", False)


async def test_vad_active_tracks_recording_callbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _FakeRecorder()
    _install_fake_realtimestt(monkeypatch, recorder)

    adapter = RealtimeSTTAdapter()
    await adapter.start(STTConfig())
    assert adapter.vad_active is False
    recorder._on_start()
    assert adapter.vad_active is True
    recorder._on_stop()
    assert adapter.vad_active is False
    await adapter.stop()


async def test_wake_mode_leaves_prefix_gating_to_speech_controller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _FakeRecorder()
    captured = _install_fake_realtimestt(monkeypatch, recorder)

    adapter = RealtimeSTTAdapter()
    await adapter.start(STTConfig(mode="wake", wake_names=["Mimi", "Hey Mimi"]))
    assert "wake_words" not in captured["kwargs"]
    await adapter.stop()


async def test_portable_default_uses_cpu_int8(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _FakeRecorder()
    captured = _install_fake_realtimestt(monkeypatch, recorder)

    adapter = RealtimeSTTAdapter()
    await adapter.start(STTConfig())

    assert captured["kwargs"]["device"] == "cpu"
    assert captured["kwargs"]["compute_type"] == "int8"
    assert captured["kwargs"]["model"] == "small.en"
    assert captured["kwargs"]["use_main_model_for_realtime"] is True
    assert captured["kwargs"]["post_speech_silence_duration"] == 1.0
    await adapter.stop()


async def test_passes_configured_end_of_speech_pause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _FakeRecorder()
    captured = _install_fake_realtimestt(monkeypatch, recorder)

    adapter = RealtimeSTTAdapter()
    await adapter.start(STTConfig(post_speech_silence_duration=1.6))

    assert captured["kwargs"]["post_speech_silence_duration"] == 1.6
    await adapter.stop()


async def test_pause_and_restart_reuses_recorder_for_a_second_final(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _FakeRecorder()
    captured = _install_fake_realtimestt(monkeypatch, recorder)
    adapter = RealtimeSTTAdapter()
    config = STTConfig(mode="dictation", prompt_terms=["Mimi", "Me me"])

    await adapter.start(config)
    recorder.queue_final("first turn")
    first = await asyncio.wait_for(anext(adapter.transcripts), timeout=0.5)
    await adapter.stop()

    await adapter.start(config)
    recorder.queue_final("second turn")
    second = await asyncio.wait_for(anext(adapter.transcripts), timeout=0.5)

    assert first.text == "first turn"
    assert second.text == "second turn"
    assert captured["calls"] == 1
    await adapter.close()


async def test_final_is_not_starved_by_realtime_preview_flood(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _FakeRecorder()
    _install_fake_realtimestt(monkeypatch, recorder)
    adapter = RealtimeSTTAdapter()
    await adapter.start(STTConfig(mode="wake"))

    for index in range(500):
        recorder._on_partial(f"preview {index}")
    assert adapter._queue.qsize() == 1

    recorder.queue_final("Mimi, send this now")

    async def _next_final():
        previews = 0
        async for item in adapter.transcripts:
            if item.is_final:
                return item, previews
            previews += 1
        raise AssertionError("transcript stream ended before its final")

    transcript, previews = await asyncio.wait_for(_next_final(), timeout=0.5)

    assert transcript.is_final is True
    assert transcript.text == "Mimi, send this now"
    assert previews <= 1
    await adapter.close()


async def test_wake_metadata_does_not_rebuild_the_same_warm_recorder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _FakeRecorder()
    captured = _install_fake_realtimestt(monkeypatch, recorder)
    adapter = RealtimeSTTAdapter()

    await adapter.start(STTConfig(mode="wake", wake_names=["Mimi"], prompt_terms=["Mimi", "Me me"]))
    await adapter.stop()
    await adapter.start(STTConfig(mode="dictation", wake_names=[], prompt_terms=["Mimi", "Me me"]))

    assert captured["calls"] == 1
    await adapter.close()
