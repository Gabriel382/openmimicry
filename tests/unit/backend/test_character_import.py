from __future__ import annotations

import io
import json
import struct
import zipfile
from pathlib import Path

import pytest
import yaml
from openmimicry_backend.character_import import CharacterImportError, CharacterRegistry

PACK = """\
schema_version: 1
id: test_friend
name: Test Friend
kind: sprite2d
emotions:
  idle:
    frames: idle
"""


def _zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_imports_single_folder_pack_and_discovers_it(tmp_path) -> None:
    registry = CharacterRegistry([str(tmp_path / "characters")])
    result = registry.install_zip(
        _zip({"friend/pack.yaml": PACK.encode(), "friend/idle/000.png": b"png"}),
        filename="friend.zip",
    )

    assert result["id"] == "test_friend"
    assert (tmp_path / "characters" / "test_friend" / "pack.yaml").is_file()
    assert registry.list()[0]["name"] == "Test Friend"


def test_rejects_zip_path_traversal_before_install(tmp_path) -> None:
    registry = CharacterRegistry([str(tmp_path / "characters")])
    with pytest.raises(CharacterImportError, match="unsafe ZIP path"):
        registry.install_zip(
            _zip({"pack/pack.yaml": PACK.encode(), "../escape.png": b"bad"}),
            filename="bad.zip",
        )
    assert not (tmp_path / "escape.png").exists()


def test_rejects_duplicate_pack_id_without_overwriting(tmp_path) -> None:
    registry = CharacterRegistry([str(tmp_path / "characters")])
    payload = _zip({"pack.yaml": PACK.encode(), "idle/000.png": b"png"})
    registry.install_zip(payload, filename="one.zip")
    with pytest.raises(CharacterImportError, match="already installed"):
        registry.install_zip(payload, filename="two.zip")


def test_character_creator_builds_every_lifecycle_state_atomically(tmp_path) -> None:
    registry = CharacterRegistry([str(tmp_path / "characters")])
    png = b"\x89PNG\r\n\x1a\n" + b"test-payload"

    result = registry.create_sprite_pack(
        pack_id="created_friend",
        name="Created Friend",
        author="Test Owner",
        license_name="MIT",
        sprites={"idle": png, "speaking": png},
    )

    root = tmp_path / "characters" / "created_friend"
    assert result["license"] == "MIT"
    assert (root / "pack.yaml").is_file()
    for state in ("idle", "listening", "thinking", "speaking", "happy", "error"):
        assert (root / state / "000.png").is_file()
        assert (root / f"{state}_speaking" / "000.png").is_file()


def test_commercial_profile_rejects_unknown_character_license(tmp_path) -> None:
    registry = CharacterRegistry([str(tmp_path / "characters")], reject_licenses=["unknown", "gpl"])
    with pytest.raises(CharacterImportError, match="license"):
        registry.install_zip(
            _zip({"pack.yaml": PACK.encode(), "idle/000.png": b"png"}),
            filename="unlicensed.zip",
        )


def test_original_vrm_archive_imports_only_model_and_credit_manifest(tmp_path) -> None:
    archive = _zip(
        {
            "creator/model/avatar.vrm": b"glTF" + b"\0" * 32,
            "creator/source.psd": b"not copied",
        }
    )
    registry = CharacterRegistry([str(tmp_path / "characters")])

    result = registry.install_vrm_archive(
        archive,
        pack_id="creator_avatar",
        name="Creator Avatar",
        author="Original Artist",
        license_name="Commercial use allowed; redistribution prohibited",
        source_url="https://example.test/original",
    )

    root = Path(result["path"])
    manifest = yaml.safe_load((root / "pack.yaml").read_text(encoding="utf-8"))
    assert (root / "character.vrm").read_bytes().startswith(b"glTF")
    assert not (root / "source.psd").exists()
    assert manifest["author"] == "Original Artist"
    assert manifest["metadata"]["private_local_import"] is True
    assert manifest["metadata"]["transform"]["rotation"] == [0.0, 180.0, 0.0]


def test_vrm_import_persists_front_facing_rotation_and_supports_export_delete(tmp_path) -> None:
    registry = CharacterRegistry([str(tmp_path / "private"), str(tmp_path / "bundled")])
    result = registry.install_vrm_archive(
        _zip({"avatar.vrm": b"glTF" + b"\0" * 32}),
        pack_id="custom_vrm",
        name="Custom VRM",
        author="User",
        license_name="Original terms",
        rotation_y=180,
    )
    manifest = yaml.safe_load((Path(result["path"]) / "pack.yaml").read_text(encoding="utf-8"))

    assert manifest["metadata"]["transform"]["rotation"] == [0.0, 180.0, 0.0]
    assert zipfile.ZipFile(io.BytesIO(registry.export_zip("custom_vrm"))).testzip() is None
    registry.delete("custom_vrm")
    with pytest.raises(CharacterImportError, match="not installed"):
        registry.resolve("custom_vrm")


def test_embedded_vrm_motion_features_are_discovered_separately(tmp_path) -> None:
    document = json.dumps(
        {
            "asset": {"version": "2.0"},
            "animations": [{"name": "Idle"}, {"name": "Talk"}],
            "extensions": {
                "VRM": {
                    "blendShapeMaster": {
                        "blendShapeGroups": [
                            {"name": "Joy", "presetName": "joy"},
                            {"name": "Sorrow", "presetName": "sorrow"},
                            {"name": "Surprised", "presetName": "unknown"},
                        ]
                    }
                }
            },
        },
        separators=(",", ":"),
    ).encode()
    document += b" " * ((4 - len(document) % 4) % 4)
    content = b"glTF" + struct.pack("<II", 2, 12 + 8 + len(document))
    content += struct.pack("<II", len(document), 0x4E4F534A) + document
    registry = CharacterRegistry([str(tmp_path / "characters")])
    registry.install_vrm_archive(
        _zip({"avatar.vrm": content}),
        pack_id="animated",
        name="Animated",
        author="Owner",
        license_name="User-owned",
    )

    assert registry.animation_clips("animated") == ["Idle", "Talk"]
    features = registry.model_features("animated")
    assert features["clips"] == ["Idle", "Talk"]
    assert features["expressions"] == ["happy", "sad", "Surprised"]
    assert features["vrm"] == "0.x"
