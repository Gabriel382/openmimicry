from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from openmimicry.voice.tts.chatterbox import ChatterboxSettings, ChatterboxTTSAdapter
from openmimicry.voice.tts.elevenlabs import ElevenLabsSettings, ElevenLabsTTSAdapter
from openmimicry.voice.tts.system_command import _commands


def test_windows_system_tts_never_interpolates_text_into_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr("shutil.which", lambda name: f"C:/Windows/{name}.exe")
    text_path = tmp_path / "utterance.txt"
    wave_path = tmp_path / "utterance.wav"
    dangerous = "'; Remove-Item -Recurse C:\\; '"
    text_path.write_text(dangerous, encoding="utf-8")

    synth, play, environment = _commands(text_path=text_path, wave_path=wave_path)

    assert dangerous not in " ".join(synth + play)
    assert environment["OPENMIMICRY_TEXT_PATH"] == str(text_path)
    assert environment["OPENMIMICRY_WAV_PATH"] == str(wave_path)


def test_elevenlabs_requires_environment_or_session_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    adapter = ElevenLabsTTSAdapter(ElevenLabsSettings(voice_id="voice"))
    with pytest.raises(RuntimeError, match="requires ELEVENLABS_API_KEY"):
        adapter._api_key()
    adapter.set_session_api_key("session-secret")
    assert adapter._api_key() == "session-secret"
    assert adapter.credential_status() == {"session": True, "environment": False}
    adapter.clear_session_api_key()
    assert adapter.has_credentials is False
    assert "session-secret" not in repr(adapter)


def test_chatterbox_requires_a_consent_record(tmp_path: Path) -> None:
    reference = tmp_path / "voice.wav"
    reference.write_bytes(b"RIFF")
    adapter = ChatterboxTTSAdapter(
        ChatterboxSettings(reference_path=str(reference), consent_record="")
    )
    with pytest.raises(RuntimeError, match="consent"):
        adapter._validate()


async def test_chatterbox_prepare_reuses_one_prewarmed_worker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class FakeInput:
        def write(self, _payload: bytes) -> None:
            return None

        async def drain(self) -> None:
            return None

    class FakeProcess:
        def __init__(self) -> None:
            self.returncode: int | None = None
            self.stdin = FakeInput()
            self.stdout = asyncio.StreamReader()
            self.stdout.feed_data(b'{"type":"ready"}\n')
            self.stdout.feed_eof()
            self.stderr = asyncio.StreamReader()
            self.stderr.feed_eof()

        def terminate(self) -> None:
            self.returncode = 0

        def kill(self) -> None:
            self.returncode = -9

        async def wait(self) -> int:
            return self.returncode or 0

    created: list[FakeProcess] = []

    async def fake_create(*_args, **_kwargs):
        process = FakeProcess()
        created.append(process)
        return process

    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"RIFFxxxxWAVEdata")
    monkeypatch.setattr(
        "openmimicry.voice.tts.chatterbox.importlib.util.find_spec", lambda _name: object()
    )
    monkeypatch.setattr(
        "openmimicry.voice.tts.chatterbox.asyncio.create_subprocess_exec", fake_create
    )
    adapter = ChatterboxTTSAdapter(
        ChatterboxSettings(reference_path=str(reference), consent_record="consent on file")
    )

    await adapter.prepare(None)  # type: ignore[arg-type]
    await adapter.prepare(None)  # type: ignore[arg-type]
    assert len(created) == 1
    assert await adapter.healthcheck() is True
    await adapter.close()


async def test_chatterbox_healthcheck_never_cold_starts_worker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"RIFFxxxxWAVEdata")
    created = 0

    async def fake_create(*_args, **_kwargs):
        nonlocal created
        created += 1
        raise AssertionError("healthcheck must not start Chatterbox")

    monkeypatch.setattr(
        "openmimicry.voice.tts.chatterbox.importlib.util.find_spec", lambda _name: object()
    )
    monkeypatch.setattr(
        "openmimicry.voice.tts.chatterbox.asyncio.create_subprocess_exec", fake_create
    )
    adapter = ChatterboxTTSAdapter(
        ChatterboxSettings(reference_path=str(reference), consent_record="consent on file")
    )

    assert await adapter.healthcheck() is False
    assert created == 0
