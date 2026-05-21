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

    def shutdown(self) -> None:
        self._stopped = True


def _install_fake_realtimestt(monkeypatch: pytest.MonkeyPatch, recorder: _FakeRecorder):
    """Inject a fake ``RealtimeSTT`` module."""

    captured: dict = {}

    def factory(**kwargs):
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
            if len(received) == 2:
                return

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)
    # Simulate RealtimeSTT's worker thread firing the partial callback.
    recorder._on_partial("partial-a")
    recorder._on_partial("partial-b")
    await asyncio.wait_for(task, timeout=0.5)

    await adapter.stop()
    assert received == [("partial-a", False), ("partial-b", False)]


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


async def test_wake_mode_sets_wake_words(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _FakeRecorder()
    captured = _install_fake_realtimestt(monkeypatch, recorder)

    adapter = RealtimeSTTAdapter()
    await adapter.start(STTConfig(mode="wake", wake_names=["Mimi", "Hey Mimi"]))
    assert captured["kwargs"]["wake_words"] == "Mimi,Hey Mimi"
    await adapter.stop()
