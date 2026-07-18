from __future__ import annotations

import io
import zipfile

import pytest
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
