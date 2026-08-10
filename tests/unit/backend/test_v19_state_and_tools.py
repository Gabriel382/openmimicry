from __future__ import annotations

from pathlib import Path

import yaml
from openmimicry.core.schemas.app import AppConfig, ToolsConfig
from openmimicry_backend.character_import import CharacterRegistry
from openmimicry_backend.companion_state import rehydrate_active_companion
from openmimicry_backend.local_tools import LocalToolService
from openmimicry_backend.voice_profiles import VoiceProfileStore


def test_startup_rehydrates_last_companion_pack_runtime_and_voice(tmp_path: Path) -> None:
    characters = tmp_path / "characters" / "private_vrm"
    characters.mkdir(parents=True)
    (characters / "character.vrm").write_bytes(b"glTF" + b"\0" * 32)
    (characters / "pack.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "private_vrm",
                "name": "Private VRM",
                "author": "User",
                "license": "User-owned",
                "kind": "vrm",
                "metadata": {"asset": {"kind": "vrm", "path": "character.vrm"}},
            }
        ),
        encoding="utf-8",
    )
    VoiceProfileStore(tmp_path).create_remote(
        profile_id="glados",
        name="GLaDOS",
        voice_id="paid-voice-id",
        consent_record="Owner consented on 2026-08-02",
    )
    companion = tmp_path / "companions" / "glados"
    companion.mkdir(parents=True)
    (companion / "companion.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "id": "glados",
                "avatar_pack": "private_vrm",
                "voice_profile": "glados",
            }
        ),
        encoding="utf-8",
    )
    config = AppConfig.model_validate(
        {
            "app": {"data_dir": str(tmp_path)},
            "avatar": {
                "pack": "octomimic",
                "runtime": "sprite2d",
                "pack_roots": [str(tmp_path / "characters")],
            },
            "companion": {"active_id": "glados"},
        }
    )

    restored = rehydrate_active_companion(config, CharacterRegistry([str(tmp_path / "characters")]))

    assert restored.avatar.pack == "private_vrm"
    assert restored.avatar.runtime == "threejs"
    assert restored.voice.active_profile == "glados"
    assert restored.voice.tts.voice == "paid-voice-id"


async def test_local_file_tool_never_speaks_file_contents(tmp_path: Path) -> None:
    service = LocalToolService(
        ToolsConfig(enabled=True, allowed_roots=[str(tmp_path)], allow_files=True),
        data_dir=str(tmp_path),
    )
    reply = await service.try_execute(
        "Write a text file named answer.txt containing this should remain silent"
    )

    assert (tmp_path / "answer.txt").read_text(encoding="utf-8") == ("this should remain silent")
    assert reply is not None and "this should remain silent" not in reply


async def test_local_alarm_tool_accepts_brazilian_24_hour_spelling(tmp_path: Path) -> None:
    service = LocalToolService(
        ToolsConfig(enabled=True, allow_alarms=True),
        data_dir=str(tmp_path),
    )

    reply = await service.try_execute("Set an alarm to 17h!")

    assert reply == "Alarm set for 17:00."
    assert (tmp_path / "tools" / "alarms.json").is_file()
    await service.close()
