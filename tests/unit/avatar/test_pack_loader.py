"""Unit tests for openmimicry.avatar.pack.loader."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from openmimicry.avatar.pack import PackLoadError, load_pack

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "packs"


def test_load_good_pack_has_all_emotions() -> None:
    pack = load_pack(FIXTURES / "good_pack")
    assert pack.id == "good_pack"
    assert set(pack.emotions) == {"idle", "happy"}
    # Frames resolved to a sorted list of file paths.
    idle = pack.emotions["idle"]
    assert isinstance(idle.frames, list)
    assert len(idle.frames) == 2
    assert all(str(f).endswith(".png") for f in idle.frames)


def test_load_good_pack_resolves_speaking_variants() -> None:
    pack = load_pack(FIXTURES / "good_pack")
    idle = pack.emotions["idle"]
    assert isinstance(idle.speaking_frames, list)
    assert len(idle.speaking_frames) == 1
    happy = pack.emotions["happy"]
    assert isinstance(happy.speaking_frames, list)
    assert len(happy.speaking_frames) == 1


def test_missing_speaking_falls_back_to_base_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        pack = load_pack(FIXTURES / "missing_speaking")
    # The loader returns successfully but logs at least one fallback warning.
    assert pack.id == "missing_speaking"
    assert any(
        "no speaking_frames" in r.getMessage() or "fall back" in r.getMessage().lower()
        for r in caplog.records
    )
    # speaking_frames falls back to base frames.
    idle = pack.emotions["idle"]
    assert idle.speaking_frames == idle.frames


def test_broken_manifest_raises_pack_load_error() -> None:
    with pytest.raises(PackLoadError):
        load_pack(FIXTURES / "broken_manifest")


def test_missing_directory_raises() -> None:
    with pytest.raises(PackLoadError):
        load_pack(FIXTURES / "this_pack_does_not_exist")


def test_missing_pack_yaml_raises(tmp_path: Path) -> None:
    with pytest.raises(PackLoadError):
        load_pack(tmp_path)


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    (tmp_path / "pack.yaml").write_text("id: x\nfoo: : :", encoding="utf-8")
    with pytest.raises(PackLoadError):
        load_pack(tmp_path)


def test_explicit_frame_list_resolves(tmp_path: Path) -> None:
    """frames can be either a folder path or an explicit file list."""
    states_dir = tmp_path / "frames"
    states_dir.mkdir()
    (states_dir / "a.png").write_bytes(b"")
    (states_dir / "b.png").write_bytes(b"")
    (tmp_path / "pack.yaml").write_text(
        "schema_version: 1\n"
        "id: explicit\n"
        "name: Explicit\n"
        "emotions:\n"
        "  idle:\n"
        "    frames: [frames/a.png, frames/b.png]\n"
        "    speaking_frames: [frames/a.png]\n",
        encoding="utf-8",
    )
    pack = load_pack(tmp_path)
    idle = pack.emotions["idle"]
    assert isinstance(idle.frames, list)
    assert len(idle.frames) == 2
    assert all(p.endswith(".png") for p in idle.frames)
