"""Regression coverage for the v1.5 child-process voice boundaries."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from openmimicry.core.schemas import STTConfig, TTSConfig
from openmimicry.voice.stt.isolated_faster_whisper import (
    IsolatedFasterWhisperAdapter,
    IsolatedFasterWhisperSettings,
)
from openmimicry.voice.tts.isolated_piper import (
    IsolatedPiperSettings,
    IsolatedPiperTTSAdapter,
)
from openmimicry.voice.workers.whisper_runtime import load_whisper_runtime


async def test_isolated_stt_reuses_warm_worker_for_multiple_ptt_turns() -> None:
    adapter = IsolatedFasterWhisperAdapter(
        settings=IsolatedFasterWhisperSettings(
            worker_module="tests.fixtures.fake_stt_service",
            startup_timeout_s=2.0,
            command_timeout_s=2.0,
        )
    )
    config = STTConfig(mode="push_to_talk", model="small.en")
    try:
        await adapter.start(config)
        assert adapter._process is not None
        first_pid = adapter._process.pid
        await adapter.finish_utterance()
        first = await asyncio.wait_for(anext(adapter.transcripts), timeout=1.0)
        await adapter.stop()

        await adapter.start(config)
        await adapter.finish_utterance()
        second = await asyncio.wait_for(anext(adapter.transcripts), timeout=1.0)

        assert adapter._process is not None
        assert adapter._process.pid == first_pid
        assert first.text == "voice turn 1"
        assert second.text == "voice turn 2"
    finally:
        await adapter.close()


async def test_isolated_piper_speaks_multiple_replies_in_fresh_processes() -> None:
    adapter = IsolatedPiperTTSAdapter(
        settings=IsolatedPiperSettings(worker_module="tests.fixtures.fake_piper_job")
    )
    adapter.prepare = AsyncMock()  # type: ignore[method-assign]
    config = TTSConfig(engine="piper", voice="fake")

    await adapter.speak("first reply", config=config)
    await adapter.speak("second reply", config=config)

    assert adapter.is_speaking is False


async def test_killing_hung_tts_does_not_poison_the_next_reply() -> None:
    adapter = IsolatedPiperTTSAdapter(
        settings=IsolatedPiperSettings(worker_module="tests.fixtures.fake_piper_job")
    )
    adapter.prepare = AsyncMock()  # type: ignore[method-assign]
    config = TTSConfig(engine="piper", voice="fake")

    try:
        hung = asyncio.create_task(adapter.speak("hang", config=config))
        while adapter._ready is None:
            await asyncio.sleep(0)
        assert await adapter.wait_until_ready(timeout_s=1.0) is True
        await adapter.stop()
        await asyncio.wait_for(hung, timeout=1.0)

        await asyncio.wait_for(adapter.speak("recovered reply", config=config), timeout=1.0)
        assert adapter.is_speaking is False
    finally:
        await adapter.close()


def test_auto_device_falls_back_when_cuda_model_load_fails() -> None:
    attempts: list[tuple[str, str]] = []

    class _FakeModel:
        def __init__(self, _name: str, *, device: str, compute_type: str) -> None:
            attempts.append((device, compute_type))
            if device == "cuda":
                raise RuntimeError("Library cublas64_12.dll is not found")

    runtime = load_whisper_runtime(
        "medium.en",
        requested_device="auto",
        requested_compute_type="auto",
        model_class=_FakeModel,
        cuda_count=lambda: 1,
    )

    assert attempts == [("cuda", "float16"), ("cpu", "int8")]
    assert runtime.device == "cpu"
    assert runtime.compute_type == "int8"
    assert "cublas64_12.dll" in str(runtime.fallback_reason)


def test_explicit_cuda_does_not_hide_a_broken_cuda_installation() -> None:
    class _BrokenCudaModel:
        def __init__(self, _name: str, *, device: str, compute_type: str) -> None:
            raise RuntimeError(f"cannot load CUDA for {device}/{compute_type}")

    with pytest.raises(RuntimeError, match="cannot load CUDA"):
        load_whisper_runtime(
            "medium.en",
            requested_device="cuda",
            requested_compute_type="float16",
            model_class=_BrokenCudaModel,
            cuda_count=lambda: 1,
        )


def test_voice_doctor_falls_back_when_cuda_fails_during_inference(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    faster_whisper = ModuleType("faster_whisper")
    ctranslate2 = ModuleType("ctranslate2")

    class _LazyFailureModel:
        def __init__(self, _name: str, *, device: str, compute_type: str) -> None:
            self.device = device
            self.compute_type = compute_type

        def transcribe(self, _path: str, **_kwargs: object):
            if self.device == "cuda":
                raise RuntimeError("Library cublas64_12.dll is not found")
            return [SimpleNamespace(text="Open Mimicry voice preflight")], SimpleNamespace()

    faster_whisper.WhisperModel = _LazyFailureModel  # type: ignore[attr-defined]
    ctranslate2.get_cuda_device_count = lambda: 1  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "faster_whisper", faster_whisper)
    monkeypatch.setitem(sys.modules, "ctranslate2", ctranslate2)

    from scripts.voice_doctor import _transcribe

    text, _elapsed, details = _transcribe(tmp_path / "sample.wav", model_name="medium.en")

    assert text == "Open Mimicry voice preflight"
    assert details["device"] == "cpu"
    assert details["compute_type"] == "int8"
    assert "cublas64_12.dll" in str(details["fallback_reason"])
