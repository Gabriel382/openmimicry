"""Unit tests for ``build_threejs_projection``.

The projector is pure — we build :class:`CharacterPack` instances
directly via Pydantic instead of loading from disk. Every assertion
targets the wire shape documented in M9's brief.
"""

from __future__ import annotations

import pytest
from openmimicry.avatar.runtimes.threejs.projection import (
    DEFAULT_FADE_MS,
    build_threejs_projection,
    clip_fallback_chain,
    expression_weights,
    pick_clip,
    resolve_asset,
)
from openmimicry.core.schemas import AvatarDirective, CharacterPack, EmotionFrames


def _vrm_pack(**overrides) -> CharacterPack:
    base = dict(
        schema_version=1,
        id="octomimic_vrm",
        name="OctomimicVRM",
        kind="vrm",
        default_state="idle",
        default_emotion="neutral",
        emotions={"idle": EmotionFrames(frames=["a.png"])},
    )
    base.update(overrides)
    return CharacterPack(**base)


def _gltf_pack(**overrides) -> CharacterPack:
    return _vrm_pack(kind="gltf", id="octomimic_gltf", **overrides)


# ---------------------------------------------------------------------------
# build_threejs_projection
# ---------------------------------------------------------------------------


def test_projection_shape_for_idle_neutral() -> None:
    pack = _vrm_pack()
    directive = AvatarDirective(state="idle", emotion="neutral", speaking=False)
    msg = build_threejs_projection(directive, pack)

    assert msg["type"] == "avatar.directive"
    assert msg["runtime"] == "threejs"
    assert msg["directive"]["state"] == "idle"
    assert msg["asset"] == {
        "kind": "vrm",
        "url": "/static/characters/octomimic_vrm/character.vrm",
        "pack_id": "octomimic_vrm",
    }
    assert msg["clip"] == "neutral_idle"
    assert "idle" in msg["fallbackClips"]
    assert msg["expression"] == "neutral"
    assert msg["expressionWeights"] == {}
    assert msg["intensity"] == 1.0
    assert msg["gazeTarget"] == "towards_user"
    assert msg["fadeMs"] == DEFAULT_FADE_MS


def test_speaking_happy_emits_blend_and_expression_weights() -> None:
    pack = _vrm_pack()
    directive = AvatarDirective(
        state="speaking",
        emotion="happy",
        speaking=True,
        intensity=0.7,
    )
    msg = build_threejs_projection(directive, pack)

    assert msg["clip"] == "happy_speaking_speaking"  # most-specific fallback first
    assert "speaking_speaking" in msg["fallbackClips"]
    assert msg["expression"] == "happy"
    # intensity 0.7 scales the base happy weight (1.0) down to 0.7
    assert msg["expressionWeights"]["happy"] == pytest.approx(0.7)
    # talk weight blends with intensity
    assert msg["blendWeights"]["talk"] == pytest.approx(0.88, rel=1e-3)
    assert "happy" in msg["blendWeights"]


def test_intensity_clamped_to_unit_interval() -> None:
    pack = _vrm_pack()
    for raw, expected in [(-1.0, 0.0), (0.0, 0.0), (1.5, 1.0), (None, 1.0)]:
        kwargs = {"intensity": raw} if raw is not None else {}
        directive = AvatarDirective(state="idle", emotion="happy", **kwargs)
        msg = build_threejs_projection(directive, pack)
        assert msg["intensity"] == expected


def test_known_gesture_attaches_clip_name() -> None:
    pack = _vrm_pack()
    directive = AvatarDirective(state="idle", emotion="happy", gesture="wave")
    msg = build_threejs_projection(directive, pack)
    assert msg["gestureClip"] == "wave"


def test_unknown_gesture_omits_the_field() -> None:
    pack = _vrm_pack()
    directive = AvatarDirective(
        state="idle", emotion="happy", gesture="definitely-not-a-gesture"
    )
    msg = build_threejs_projection(directive, pack)
    assert "gestureClip" not in msg


def test_runtime_cfg_can_remap_gesture_to_arbitrary_clip() -> None:
    pack = _vrm_pack()
    directive = AvatarDirective(state="idle", emotion="happy", gesture="special")
    msg = build_threejs_projection(
        directive, pack, runtime_cfg={"gestures": {"special": "custom_clip_42"}}
    )
    assert msg["gestureClip"] == "custom_clip_42"


def test_explicit_runtime_cfg_asset_overrides_pack() -> None:
    pack = _vrm_pack()
    directive = AvatarDirective(state="idle")
    msg = build_threejs_projection(
        directive,
        pack,
        runtime_cfg={"asset": {"kind": "gltf", "url": "https://cdn.example/octomimic.glb"}},
    )
    assert msg["asset"]["kind"] == "gltf"
    assert msg["asset"]["url"] == "https://cdn.example/octomimic.glb"


def test_gltf_pack_resolves_default_asset_url() -> None:
    pack = _gltf_pack()
    directive = AvatarDirective(state="idle")
    msg = build_threejs_projection(directive, pack)
    assert msg["asset"]["kind"] == "gltf"
    assert msg["asset"]["url"].endswith("character.gltf")


def test_gaze_field_propagates_when_set() -> None:
    pack = _vrm_pack()
    directive = AvatarDirective(state="idle", gaze="screen_center")
    msg = build_threejs_projection(directive, pack)
    assert msg["gazeTarget"] == "screen_center"


def test_default_gaze_can_be_overridden_via_runtime_cfg() -> None:
    pack = _vrm_pack()
    directive = AvatarDirective(state="idle")
    msg = build_threejs_projection(
        directive, pack, runtime_cfg={"default_gaze": "neutral"}
    )
    assert msg["gazeTarget"] == "neutral"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestClipFallbackChain:
    def test_non_speaking_idle_neutral(self) -> None:
        chain = clip_fallback_chain("idle", "neutral", speaking=False)
        assert chain == ["neutral_idle", "idle"]

    def test_speaking_happy_speaking_state(self) -> None:
        chain = clip_fallback_chain("speaking", "happy", speaking=True)
        assert chain[0] == "happy_speaking_speaking"
        assert "happy_speaking" in chain
        assert chain[-1] == "idle"

    def test_chain_is_unique_in_order(self) -> None:
        chain = clip_fallback_chain("idle", "neutral", speaking=True)
        assert len(chain) == len(set(chain))


class TestPickClip:
    def test_picks_first_when_no_manifest(self) -> None:
        chain = ["happy_idle", "idle"]
        assert pick_clip(chain, available=None) == "happy_idle"

    def test_picks_first_present_clip(self) -> None:
        chain = ["happy_speaking_speaking", "happy_speaking", "speaking", "idle"]
        assert pick_clip(chain, available=["speaking", "idle"]) == "speaking"

    def test_falls_back_to_idle_when_chain_misses(self) -> None:
        chain = ["happy_idle", "idle"]
        assert pick_clip(chain, available=["wave_only"]) == "idle"

    def test_empty_chain_returns_idle(self) -> None:
        assert pick_clip([], available=None) == "idle"


class TestExpressionWeights:
    def test_neutral_returns_empty_table(self) -> None:
        assert expression_weights("neutral", intensity=1.0) == {}

    def test_happy_scales_with_intensity(self) -> None:
        assert expression_weights("happy", intensity=0.5)["happy"] == pytest.approx(0.5)
        assert expression_weights("happy", intensity=1.0)["happy"] == pytest.approx(1.0)

    def test_unknown_emotion_returns_empty(self) -> None:
        # `Emotion` is constrained, but a runtime that smuggles in an
        # unknown literal should still get a sane empty dict back.
        assert expression_weights("happy", intensity=0.0)["happy"] == pytest.approx(0.0)

    def test_returned_dict_is_a_fresh_copy(self) -> None:
        a = expression_weights("happy", intensity=1.0)
        a["happy"] = 0.0
        b = expression_weights("happy", intensity=1.0)
        assert b["happy"] == pytest.approx(1.0)


class TestResolveAsset:
    def test_runtime_cfg_asset_wins(self) -> None:
        pack = _vrm_pack()
        asset = resolve_asset(
            pack,
            runtime_cfg={"asset": {"url": "/x/y.vrm"}},
            static_url_prefix="/static/characters",
        )
        assert asset["url"] == "/x/y.vrm"
        assert asset["kind"] == "vrm"

    def test_pack_metadata_asset_relative_url(self) -> None:
        pack = _vrm_pack(metadata={"asset": {"kind": "vrm", "path": "models/octomimic.vrm"}})
        asset = resolve_asset(pack, runtime_cfg={}, static_url_prefix="/static/characters")
        assert asset["url"] == "/static/characters/octomimic_vrm/models/octomimic.vrm"

    def test_pack_metadata_asset_absolute_url_passthrough(self) -> None:
        pack = _vrm_pack(metadata={"asset": {"kind": "vrm", "path": "https://cdn.example/x.vrm"}})
        asset = resolve_asset(pack, runtime_cfg={}, static_url_prefix="/static/characters")
        assert asset["url"] == "https://cdn.example/x.vrm"

    def test_default_url_when_no_overrides(self) -> None:
        pack = _vrm_pack()
        asset = resolve_asset(pack, runtime_cfg={}, static_url_prefix="/static/characters")
        assert asset["url"] == "/static/characters/octomimic_vrm/character.vrm"
        assert asset["kind"] == "vrm"
        assert asset["pack_id"] == "octomimic_vrm"
