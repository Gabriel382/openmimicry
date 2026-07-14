"""Unit tests for ``build_live3d_projection`` and ``resolve_live_config``.

The projector is pure — packs are constructed via Pydantic, no disk IO.
"""

from __future__ import annotations

import pytest
from openmimicry.avatar.runtimes.live3d.projection import (
    DEFAULT_BLEND_WINDOW_MS,
    build_live3d_projection,
    resolve_live_config,
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


# ---------------------------------------------------------------------------
# build_live3d_projection
# ---------------------------------------------------------------------------


def test_live3d_inherits_threejs_shape_with_runtime_swapped() -> None:
    pack = _vrm_pack()
    directive = AvatarDirective(state="idle", emotion="neutral", speaking=False)
    msg = build_live3d_projection(directive, pack)

    assert msg["type"] == "avatar.directive"
    assert msg["runtime"] == "live3d"
    # The Three.js fields all survive the projection.
    assert "asset" in msg
    assert "clip" in msg
    assert "fallbackClips" in msg
    assert "expressionWeights" in msg
    assert "gazeTarget" in msg


def test_live3d_appends_live_block_with_defaults() -> None:
    pack = _vrm_pack()
    msg = build_live3d_projection(AvatarDirective(state="idle"), pack)
    live = msg["live"]
    assert live["mouth_driver"] == "amplitude"
    assert live["gaze_driver"] == "smooth"
    assert live["procedural_idle"] is True
    assert live["blend_window_ms"] == DEFAULT_BLEND_WINDOW_MS
    assert live["intensity"] == 1.0


def test_amplitude_block_is_present_by_default() -> None:
    pack = _vrm_pack()
    msg = build_live3d_projection(AvatarDirective(state="idle"), pack)
    assert "amplitude" in msg["live"]
    block = msg["live"]["amplitude"]
    assert block["smoothing_ms"] == 80
    assert block["gain"] == pytest.approx(1.0)


def test_viseme_block_replaces_amplitude_when_selected() -> None:
    pack = _vrm_pack()
    msg = build_live3d_projection(
        AvatarDirective(state="speaking", speaking=True),
        pack,
        runtime_cfg={"mouth_driver": "viseme"},
    )
    assert "amplitude" not in msg["live"]
    assert msg["live"]["mouth_driver"] == "viseme"
    assert msg["live"]["viseme"]["default"] == "neutral"


def test_off_mouth_driver_omits_both_blocks() -> None:
    pack = _vrm_pack()
    msg = build_live3d_projection(
        AvatarDirective(state="idle"), pack, runtime_cfg={"mouth_driver": "off"}
    )
    assert msg["live"]["mouth_driver"] == "off"
    assert "amplitude" not in msg["live"]
    assert "viseme" not in msg["live"]


def test_procedural_idle_can_be_disabled() -> None:
    pack = _vrm_pack()
    msg = build_live3d_projection(
        AvatarDirective(state="idle"), pack, runtime_cfg={"procedural_idle": False}
    )
    assert msg["live"]["procedural_idle"] is False
    assert "idle" not in msg["live"]


def test_idle_block_has_breathing_and_saccade_defaults() -> None:
    pack = _vrm_pack()
    msg = build_live3d_projection(AvatarDirective(state="idle"), pack)
    idle = msg["live"]["idle"]
    assert idle["breathing_period_ms"] == 4200
    assert idle["saccade_min_ms"] <= idle["saccade_max_ms"]
    assert idle["breathing_amplitude"] == pytest.approx(0.02)


def test_directive_gaze_propagates_into_live_block() -> None:
    pack = _vrm_pack()
    msg = build_live3d_projection(
        AvatarDirective(state="idle", gaze="away"), pack
    )
    assert msg["live"]["gaze_target"] == "away"


def test_directive_intensity_clamped_into_live_block() -> None:
    pack = _vrm_pack()
    msg = build_live3d_projection(
        AvatarDirective(state="idle", intensity=2.0), pack
    )
    assert msg["live"]["intensity"] == 1.0


# ---------------------------------------------------------------------------
# resolve_live_config — edge cases
# ---------------------------------------------------------------------------


def test_unknown_mouth_driver_falls_back_to_amplitude() -> None:
    live = resolve_live_config(
        AvatarDirective(state="idle"), runtime_cfg={"mouth_driver": "telepathy"}
    )
    assert live["mouth_driver"] == "amplitude"


def test_unknown_gaze_driver_falls_back_to_smooth() -> None:
    live = resolve_live_config(
        AvatarDirective(state="idle"), runtime_cfg={"gaze_driver": "yeet"}
    )
    assert live["gaze_driver"] == "smooth"


def test_string_bool_coercion_for_procedural_idle() -> None:
    live = resolve_live_config(
        AvatarDirective(state="idle"), runtime_cfg={"procedural_idle": "off"}
    )
    assert live["procedural_idle"] is False


def test_int_coercion_clamps_blend_window_ms() -> None:
    live_lo = resolve_live_config(
        AvatarDirective(state="idle"), runtime_cfg={"blend_window_ms": -50}
    )
    live_hi = resolve_live_config(
        AvatarDirective(state="idle"), runtime_cfg={"blend_window_ms": 999_999}
    )
    assert live_lo["blend_window_ms"] == 0
    assert live_hi["blend_window_ms"] == 10_000


def test_garbage_blend_window_falls_back_to_default() -> None:
    live = resolve_live_config(
        AvatarDirective(state="idle"), runtime_cfg={"blend_window_ms": "lol"}
    )
    assert live["blend_window_ms"] == DEFAULT_BLEND_WINDOW_MS


def test_amplitude_block_respects_overrides_and_clamps() -> None:
    live = resolve_live_config(
        AvatarDirective(state="idle"),
        runtime_cfg={
            "mouth_driver": "amplitude",
            "amplitude": {"smoothing_ms": 999_999, "gain": 50, "open_curve": 9},
        },
    )
    assert live["amplitude"]["smoothing_ms"] == 2000
    assert live["amplitude"]["gain"] == 10.0
    # open_curve goes through coerce_float (capped at 4) then clamp01 -> 1.0
    assert live["amplitude"]["open_curve"] == pytest.approx(1.0)


def test_runtime_cfg_none_safe() -> None:
    # Passing `runtime_cfg=None` shouldn't raise.
    live = resolve_live_config(AvatarDirective(state="idle"), runtime_cfg=None)
    assert "mouth_driver" in live
