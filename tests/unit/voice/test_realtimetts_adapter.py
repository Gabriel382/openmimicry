"""Unit tests for RealtimeTTSAdapter.

We inject a fake ``RealtimeTTS`` module via ``sys.modules``.
"""

from __future__ import annotations

import asyncio
import sys
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

    def feed(self, text: str) -> None:
        self.fed.append(text)

    def play_async(self) -> None:
        self.play_calls += 1
        self._playing = True

    def is_playing(self) -> bool:
        return self._playing

    def stop(self) -> None:
        self.stop_calls += 1
        self._playing = False


class _FakeEngine:
    def __init__(self, name: str, voice: str = "x"):
        self.name = name
        self.voice = voice


_LAST_STREAM: dict[str, _FakeStream] = {}


def _install_fake_realtimetts(monkeypatch: pytest.MonkeyPatch):
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

    async def finish_quickly():
        await asyncio.sleep(0.05)
        s = _LAST_STREAM["s"]
        s._playing = False

    speak_task = asyncio.create_task(adapter.speak("hello", config=TTSConfig()))
    finish_task = asyncio.create_task(finish_quickly())
    await asyncio.wait_for(speak_task, timeout=1.0)
    await finish_task

    s = _LAST_STREAM["s"]
    assert s.fed == ["hello"]
    assert s.play_calls == 1


async def test_stop_cancels_play(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_realtimetts(monkeypatch)
    adapter = RealtimeTTSAdapter()

    speak_task = asyncio.create_task(
        adapter.speak("long sentence " * 20, config=TTSConfig())
    )
    await asyncio.sleep(0.04)
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

    async def finish_quickly():
        await asyncio.sleep(0.05)
        if "s" in _LAST_STREAM:
            _LAST_STREAM["s"]._playing = False

    speak_task = asyncio.create_task(adapter.speak(gen(), config=TTSConfig()))
    finish_task = asyncio.create_task(finish_quickly())
    await asyncio.wait_for(speak_task, timeout=1.0)
    await finish_task

    s = _LAST_STREAM["s"]
    assert s.fed == ["a", "b"]
