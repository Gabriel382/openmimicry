"""Unit tests for RealtimeTTSAdapter.

We inject a fake ``RealtimeTTS`` module via ``sys.modules``.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
import threading
import types

import pytest
from openmimicry.core.schemas import TTSConfig
from openmimicry.voice.tts.realtimetts_adapter import (
    RealtimeTTSAdapter,
    RealtimeTTSUnavailable,
)


class _FakeStream:
    def __init__(self, engine):
        self.engine = engine
        self.fed: list[str] = []
        self._playing = False
        self.play_calls = 0
        self.stop_calls = 0
        self.started = threading.Event()
        self.finished = threading.Event()

    def feed(self, text: str) -> None:
        self.fed.append(text)

    def play(self) -> None:
        self.play_calls += 1
        self._playing = True
        self.started.set()
        self.finished.wait(timeout=0.08)
        self._playing = False

    def stop(self) -> None:
        self.stop_calls += 1
        self._playing = False
        self.finished.set()


class _FakeEngine:
    def __init__(self, name: str, voice: str = "x"):
        self.name = name
        self.voice = voice


_LAST_STREAM: dict[str, _FakeStream] = {}


def _install_fake_realtimetts(monkeypatch: pytest.MonkeyPatch):
    _LAST_STREAM.clear()

    def stream_factory(engine):
        s = _FakeStream(engine)
        _LAST_STREAM["s"] = s
        return s

    fake = types.SimpleNamespace(
        TextToAudioStream=stream_factory,
        SystemEngine=lambda **kw: _FakeEngine("system", **kw),
        CoquiEngine=lambda **kw: _FakeEngine("coqui", **kw),
    )
    monkeypatch.setitem(sys.modules, "RealtimeTTS", fake)


async def test_unavailable_when_realtimetts_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "RealtimeTTS", raising=False)
    monkeypatch.setattr(
        "openmimicry.voice.tts.realtimetts_adapter._import_stream_class",
        lambda: (_ for _ in ()).throw(RealtimeTTSUnavailable("not installed")),
    )
    adapter = RealtimeTTSAdapter()
    assert await adapter.healthcheck() is False


async def test_speak_string_feeds_and_plays(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_realtimetts(monkeypatch)
    adapter = RealtimeTTSAdapter()

    await asyncio.wait_for(adapter.speak("hello", config=TTSConfig()), timeout=1.0)

    s = _LAST_STREAM["s"]
    assert s.fed == ["hello"]
    assert s.play_calls == 1


async def test_stop_cancels_play(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_realtimetts(monkeypatch)
    adapter = RealtimeTTSAdapter()

    speak_task = asyncio.create_task(adapter.speak("long sentence " * 20, config=TTSConfig()))
    await asyncio.wait_for(asyncio.to_thread(lambda: _wait_for_stream_start()), timeout=0.5)
    assert adapter.is_speaking is True

    await adapter.stop()
    await asyncio.wait_for(speak_task, timeout=0.5)
    assert _LAST_STREAM["s"].stop_calls >= 1
    assert adapter.is_speaking is False


async def test_speak_async_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_realtimetts(monkeypatch)
    adapter = RealtimeTTSAdapter()

    async def gen():
        yield "a"
        yield "b"

    await asyncio.wait_for(adapter.speak(gen(), config=TTSConfig()), timeout=1.0)

    s = _LAST_STREAM["s"]
    assert s.fed == ["a", "b"]


async def test_sequential_replies_each_wait_for_playback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_realtimetts(monkeypatch)
    adapter = RealtimeTTSAdapter()

    await adapter.speak("first", config=TTSConfig())
    first = _LAST_STREAM["s"]
    await adapter.speak("second", config=TTSConfig())
    second = _LAST_STREAM["s"]

    assert first is not second
    assert first.engine is second.engine
    assert first.fed == ["first"]
    assert second.fed == ["second"]
    assert first.play_calls == second.play_calls == 1


async def test_cancelled_playback_drains_worker_before_next_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_realtimetts(monkeypatch)
    adapter = RealtimeTTSAdapter()

    first_task = asyncio.create_task(adapter.speak("first", config=TTSConfig()))
    await asyncio.wait_for(asyncio.to_thread(_wait_for_stream_start), timeout=0.5)
    first_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await first_task

    await asyncio.wait_for(adapter.speak("second", config=TTSConfig()), timeout=1.0)

    assert _LAST_STREAM["s"].fed == ["second"]
    assert _LAST_STREAM["s"].play_calls == 1
    await adapter.close()


async def test_blocking_stop_rotates_worker_and_second_reply_still_plays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop_release = threading.Event()
    play_release = threading.Event()
    streams: list[_FakeStream] = []

    class _BlockingStream(_FakeStream):
        def play(self) -> None:
            self.play_calls += 1
            self._playing = True
            self.started.set()
            play_release.wait(timeout=2.0)
            self._playing = False

        def stop(self) -> None:
            self.stop_calls += 1
            stop_release.wait(timeout=2.0)

    def stream_factory(engine):
        stream: _FakeStream = _BlockingStream(engine) if not streams else _FakeStream(engine)
        streams.append(stream)
        return stream

    fake = types.SimpleNamespace(
        TextToAudioStream=stream_factory,
        SystemEngine=lambda **kw: _FakeEngine("system", **kw),
    )
    monkeypatch.setitem(sys.modules, "RealtimeTTS", fake)
    monkeypatch.setattr(
        "openmimicry.voice.tts.realtimetts_adapter._STOP_CALL_TIMEOUT_SECONDS",
        0.03,
    )
    monkeypatch.setattr(
        "openmimicry.voice.tts.realtimetts_adapter._WORKER_DRAIN_TIMEOUT_SECONDS",
        0.03,
    )
    adapter = RealtimeTTSAdapter()

    first_task = asyncio.create_task(adapter.speak("first", config=TTSConfig()))
    while not streams:
        await asyncio.sleep(0.001)
    await asyncio.wait_for(asyncio.to_thread(streams[0].started.wait, 0.4), timeout=0.5)
    first_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.wait_for(first_task, timeout=0.3)

    await asyncio.wait_for(adapter.speak("second", config=TTSConfig()), timeout=0.5)

    assert len(streams) == 2
    assert streams[1].fed == ["second"]
    assert streams[1].play_calls == 1

    # Let the retired test worker and its daemon stop helper exit cleanly.
    stop_release.set()
    play_release.set()
    await asyncio.sleep(0.05)
    await adapter.close()


def _wait_for_stream_start() -> None:
    while "s" not in _LAST_STREAM:
        threading.Event().wait(0.001)
    assert _LAST_STREAM["s"].started.wait(timeout=0.4)
