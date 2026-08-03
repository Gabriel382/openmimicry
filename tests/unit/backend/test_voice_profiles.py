from __future__ import annotations

import io
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import yaml
from openmimicry_backend.appearance import load_appearance
from openmimicry_backend.character_import import CharacterRegistry
from openmimicry_backend.routes import companions
from openmimicry_backend.voice_profiles import VoiceProfileError, VoiceProfileStore

WAV = b"RIFF\x24\x00\x00\x00WAVEfmt reference"


def test_named_reference_profiles_are_listed_and_resolved(tmp_path: Path) -> None:
    store = VoiceProfileStore(tmp_path)

    first = store.create_reference(
        profile_id="alice",
        name="Alice",
        consent_record="Alice consented on 2026-07-19",
        filename="alice.wav",
        audio=WAV,
    )
    store.create_remote(
        profile_id="narrator",
        name="Narrator",
        voice_id="eleven-voice-id",
        consent_record="Owner consented on 2026-07-19",
    )

    assert first["reference_configured"] is True
    assert [item["id"] for item in store.list()] == ["alice", "narrator"]
    profile, directory = store.resolve("alice")
    assert profile["provider"] == "chatterbox-local"
    assert (directory / "reference.wav").read_bytes() == WAV


def test_voice_export_excludes_biometric_audio_by_default(tmp_path: Path) -> None:
    store = VoiceProfileStore(tmp_path)
    store.create_reference(
        profile_id="alice",
        name="Alice",
        consent_record="Alice consented on 2026-07-19",
        filename="alice.wav",
        audio=WAV,
    )

    with zipfile.ZipFile(io.BytesIO(store.export("alice", include_reference=False))) as archive:
        assert archive.namelist() == ["profile.yaml"]
        profile = yaml.safe_load(archive.read("profile.yaml"))
        assert profile["reference"] is None


def test_voice_reference_import_requires_explicit_confirmation(tmp_path: Path) -> None:
    source = VoiceProfileStore(tmp_path / "source")
    source.create_reference(
        profile_id="alice",
        name="Alice",
        consent_record="Alice consented on 2026-07-19",
        filename="alice.wav",
        audio=WAV,
    )
    bundle = source.export("alice", include_reference=True)
    destination = VoiceProfileStore(tmp_path / "destination")

    with pytest.raises(VoiceProfileError, match="confirm biometric"):
        destination.import_zip(bundle, confirm_reference=False)

    imported = destination.import_zip(bundle, confirm_reference=True)
    assert imported["id"] == "alice"
    assert imported["reference_configured"] is True


def test_voice_profile_import_rejects_traversal(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../profile.yaml", "schema_version: 1")

    with pytest.raises(VoiceProfileError, match="unsafe path"):
        VoiceProfileStore(tmp_path).import_zip(buffer.getvalue(), confirm_reference=False)


def test_dashboard_exposes_voice_and_companion_profile_controls() -> None:
    root = Path(__file__).resolve().parents[3]
    html = (root / "apps/backend/src/openmimicry_backend/static/dashboard.html").read_text(
        encoding="utf-8"
    )
    script = (root / "apps/backend/src/openmimicry_backend/static/dashboard.js").read_text(
        encoding="utf-8"
    )

    for element_id in (
        "voice-profile-select",
        "voice-profile-import-form",
        "companion-export-form",
        "companion-import-form",
        "companion-select",
    ):
        assert f'id="{element_id}"' in html
    assert 'fetch("/voice/profiles")' in script
    assert 'fetch("/companions")' in script
    assert "include_voice_reference" in script


class _Request:
    def __init__(self, state, body: bytes = b"") -> None:
        self.app = SimpleNamespace(state=state)
        self._content = body

    async def body(self) -> bytes:
        return self._content


async def test_whole_companion_export_and_import_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(__file__).resolve().parents[3]
    personality = tmp_path / "personality.yml"
    personality.write_text("system_prompt: Be kind and concise.\n", encoding="utf-8")
    monkeypatch.setenv("OPENMIMICRY_PERSONALITY_PATH", str(personality))
    state = SimpleNamespace(
        active_pack="octomimic",
        active_voice_profile=None,
        character_registry=CharacterRegistry([str(root / "characters")]),
        appearance=load_appearance(root / "config/theme.yml"),
        config=SimpleNamespace(app=SimpleNamespace(data_dir=str(tmp_path / "source-data"))),
    )

    exported = await companions.export_current_companion(
        _Request(state),  # type: ignore[arg-type]
        companion_id="octo_backup",
        name="Octo backup",
        include_voice_reference=False,
    )
    with zipfile.ZipFile(io.BytesIO(exported.body)) as archive:
        assert "companion.yaml" in archive.namelist()
        assert "personality/personality.yaml" in archive.namelist()
        assert any(name.startswith("avatar/octomimic/") for name in archive.namelist())

    destination = tmp_path / "destination-data"
    import_state = SimpleNamespace(
        config=SimpleNamespace(app=SimpleNamespace(data_dir=str(destination)))
    )
    imported = await companions.import_companion(
        _Request(import_state, exported.body),  # type: ignore[arg-type]
        filename="octo_backup.omprofile.zip",
        confirm_voice_reference=False,
    )

    assert cast(dict[str, Any], imported)["companion"]["id"] == "octo_backup"
    assert (destination / "companions/octo_backup/companion.yaml").is_file()
