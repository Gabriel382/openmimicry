from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from openmimicry.core.config import load as load_config
from openmimicry.memory import NullMemory
from openmimicry_backend.appearance import load_appearance
from openmimicry_backend.routes import interaction, memory, personality, voice_clone

ROOT = Path(__file__).resolve().parents[3]


class FakeRequest:
    def __init__(self, *, state, body: bytes = b"") -> None:
        self.app = SimpleNamespace(state=state)
        self._body = body

    async def body(self) -> bytes:
        return self._body


async def test_interaction_settings_hot_apply_and_persist(monkeypatch, tmp_path: Path) -> None:
    persisted: list[dict[str, object]] = []
    monkeypatch.setattr(interaction, "persist_interaction_settings", persisted.append)
    values = interaction.ResponsePresentationConfig(
        mode="voice_ready",
        minimum_ms=3000,
        base_ms=2000,
        ms_per_character=70,
        maximum_ms=40000,
    )
    state = SimpleNamespace(
        presentation_state={"value": None},
        appearance=load_appearance(tmp_path / "missing.yml"),
    )

    response = await interaction.update_interaction_settings(
        values,
        FakeRequest(state=state),  # type: ignore[arg-type]
    )

    assert response["mode"] == "voice_ready"
    assert state.presentation_state["value"] is values
    assert state.appearance.behaviour.bubble.ms_per_character == 70
    assert persisted[0]["maximum_ms"] == 40000


async def test_memory_settings_never_enable_raw_audio(monkeypatch) -> None:
    persisted: list[dict[str, object]] = []
    monkeypatch.setattr(memory, "persist_memory_settings", persisted.append)
    config = load_config(ROOT / "config/profiles/basic.yaml", env={})
    request = FakeRequest(state=SimpleNamespace(config=config, memory=NullMemory()))
    values = memory.MemorySettingsInput(
        enabled=True,
        provider="local",
        extraction_mode="deterministic",
    )

    response = await memory.update_memory_settings(
        values,
        request,  # type: ignore[arg-type]
    )

    assert response["restart_required"] is True
    assert persisted[0]["store_raw_audio"] is False


@pytest.mark.parametrize(
    ("provider", "endpoint", "expected_message"),
    [
        ("none", None, "Select Local SQLite or Hindsight"),
        ("hindsight", None, "A Hindsight endpoint is required"),
    ],
)
async def test_invalid_enabled_memory_settings_return_422_without_persisting(
    monkeypatch,
    provider: str,
    endpoint: str | None,
    expected_message: str,
) -> None:
    persisted: list[dict[str, object]] = []
    monkeypatch.setattr(memory, "persist_memory_settings", persisted.append)
    config = load_config(ROOT / "config/profiles/basic.yaml", env={})
    request = FakeRequest(state=SimpleNamespace(config=config, memory=NullMemory()))
    values = memory.MemorySettingsInput(
        enabled=True,
        provider=provider,
        endpoint=endpoint,
        extraction_mode="deterministic",
    )

    with pytest.raises(HTTPException) as exc_info:
        await memory.update_memory_settings(
            values,
            request,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 422
    assert expected_message in str(exc_info.value.detail)
    assert persisted == []


async def test_personality_update_is_atomic_and_preserves_guardrails(
    monkeypatch, tmp_path: Path
) -> None:
    target = tmp_path / "personality.yml"
    target.write_text(
        "system_prompt: old\nbehavior:\n  structured_avatar_output: true\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENMIMICRY_PERSONALITY_PATH", str(target))

    response = await personality.update_personality(
        personality.PersonalityRequest(system_prompt="Be precise and kind.")
    )

    assert response["system_prompt"] == "Be precise and kind."
    assert response["structured_avatar_output"] is True
    assert not target.with_suffix(".yml.tmp").exists()


async def test_failed_clone_settings_transaction_removes_reference(
    monkeypatch, tmp_path: Path
) -> None:
    def fail_persist(**_values) -> None:
        raise OSError("settings unavailable")

    monkeypatch.setattr(voice_clone, "persist_tts_clone", fail_persist)
    config = SimpleNamespace(app=SimpleNamespace(data_dir=str(tmp_path)))
    request = FakeRequest(
        state=SimpleNamespace(config=config),
        body=b"RIFFxxxxWAVEreference-data",
    )

    with pytest.raises(OSError, match="settings unavailable"):
        await voice_clone.upload_clone_reference(
            request,  # type: ignore[arg-type]
            filename="reference.wav",
            consent_record="Speaker consented on 2026-07-18",
        )

    references = tmp_path / "voices" / "references"
    assert not references.exists() or list(references.iterdir()) == []


async def test_voice_session_token_is_never_returned_or_persisted() -> None:
    class FakeElevenLabs:
        name = "elevenlabs"

        def __init__(self) -> None:
            self.token: str | None = None

        def set_session_api_key(self, value: str) -> None:
            self.token = value

        def clear_session_api_key(self) -> None:
            self.token = None

        def credential_status(self) -> dict[str, bool]:
            return {"session": self.token is not None, "environment": False}

    tts = FakeElevenLabs()
    request = FakeRequest(state=SimpleNamespace(wiring=SimpleNamespace(tts=tts)))
    response = await voice_clone.update_voice_credentials(
        voice_clone.VoiceCredentialRequest(action="set", token="private-token"),
        request,  # type: ignore[arg-type]
    )

    assert tts.token == "private-token"
    assert response["credentials"] == {"session": True, "environment": False}
    assert "private-token" not in repr(response)
