"""Unit tests for build_sprite2d_projection."""

from __future__ import annotations

from pathlib import Path

import pytest
from openmimicry.avatar.pack import load_pack
from openmimicry.avatar.runtimes.sprite2d.projection import (
    build_sprite2d_projection,
    frames_for_directive,
)
from openmimicry.core.schemas import AvatarDirective

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "packs"


@pytest.fixture
def pack():
    return load_pack(FIXTURES / "good_pack")


def test_projection_shape(pack) -> None:
    directive = AvatarDirective(state="idle", emotion="neutral", speaking=False)
    msg = build_sprite2d_projection(directive, pack)
    assert msg["type"] == "avatar.directive"
    assert msg["runtime"] == "sprite2d"
    assert isinstance(msg["frames"], list)
    assert msg["fps"] == 8
    assert msg["loop"] is True
    assert msg["directive"]["state"] == "idle"


def test_idle_non_speaking_uses_base_frames(pack) -> None:
    directive = AvatarDirective(state="idle", speaking=False)
    msg = build_sprite2d_projection(directive, pack)
    # 2 base idle frames in good_pack fixture.
    assert len(msg["frames"]) == 2
    assert all("idle_speaking" not in f for f in msg["frames"])


def test_idle_speaking_uses_speaking_frames(pack) -> None:
    directive = AvatarDirective(state="idle", speaking=True)
    msg = build_sprite2d_projection(directive, pack)
    # 1 idle_speaking frame in good_pack fixture.
    assert len(msg["frames"]) == 1
    assert any("idle_speaking" in f for f in msg["frames"])


def test_speaking_falls_back_to_base_when_speaking_frames_missing() -> None:
    """If a pack has no speaking_frames for the state, fall back to base."""
    pack = load_pack(FIXTURES / "missing_speaking")
    directive = AvatarDirective(state="idle", speaking=True)
    msg = build_sprite2d_projection(directive, pack)
    # The loader already filled speaking_frames with base frames, so the
    # selection should match the base frames.
    base = frames_for_directive(AvatarDirective(state="idle", speaking=False), pack)
    speaking = frames_for_directive(directive, pack)
    assert speaking == base


def test_unknown_state_falls_back_to_default(pack) -> None:
    directive = AvatarDirective(state="thinking", speaking=False)  # not in good_pack
    msg = build_sprite2d_projection(directive, pack)
    # Falls back to default_state (idle); same number of frames as idle base.
    assert len(msg["frames"]) == 2


def test_happy_uses_happy_frames_and_loop_false(pack) -> None:
    directive = AvatarDirective(state="happy", speaking=False)
    msg = build_sprite2d_projection(directive, pack)
    assert msg["fps"] == 12
    assert msg["loop"] is False
    assert len(msg["frames"]) == 1


def test_static_url_rewrites_paths(pack) -> None:
    directive = AvatarDirective(state="idle", speaking=False)
    msg = build_sprite2d_projection(directive, pack)
    for url in msg["frames"]:
        # Default prefix is /static/characters; pack.id is good_pack.
        assert url.startswith("/static/characters/good_pack/")
        assert url.endswith(".png")


def test_custom_url_prefix(pack) -> None:
    directive = AvatarDirective(state="idle", speaking=False)
    msg = build_sprite2d_projection(
        directive, pack, static_url_prefix="/assets/packs"
    )
    for url in msg["frames"]:
        assert url.startswith("/assets/packs/good_pack/")
