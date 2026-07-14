"""``build_live3d_projection`` — extend the M9 Three.js wire shape.

The output mirrors :func:`build_threejs_projection` exactly, except for
two changes:

* ``runtime: "live3d"`` so the frontend routes to ``Live3DRuntime``.
* A new top-level ``live`` block carrying the per-driver config the
  frontend needs to enable mouth / idle / gaze drivers::

      "live": {
          "mouth_driver": "amplitude" | "viseme" | "off",
          "gaze_driver":  "smooth" | "snap" | "off",
          "procedural_idle": true,
          "blend_window_ms": 200,
          "intensity": 0.7
      }

The projector is pure (same rule as M9): no disk IO, never raises.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from openmimicry.core.schemas import AvatarDirective, CharacterPack

from ..threejs.projection import build_threejs_projection

__all__ = [
    "DEFAULT_BLEND_WINDOW_MS",
    "MouthDriver",
    "GazeDriver",
    "build_live3d_projection",
    "resolve_live_config",
]


_log = logging.getLogger(__name__)


DEFAULT_BLEND_WINDOW_MS: int = 200

MouthDriver = Literal["amplitude", "viseme", "off"]
GazeDriver = Literal["smooth", "snap", "off"]

_VALID_MOUTH_DRIVERS: frozenset[str] = frozenset({"amplitude", "viseme", "off"})
_VALID_GAZE_DRIVERS: frozenset[str] = frozenset({"smooth", "snap", "off"})


def build_live3d_projection(
    directive: AvatarDirective,
    pack: CharacterPack,
    *,
    static_url_prefix: str = "/static/characters",
    runtime_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the Live3D wire message.

    Starts from the M9 Three.js projection so the frontend can mount
    the same scene + character controller, then patches ``runtime`` and
    appends a ``live`` block.
    """
    runtime_cfg = dict(runtime_cfg or {})
    message = build_threejs_projection(
        directive,
        pack,
        static_url_prefix=static_url_prefix,
        runtime_cfg=runtime_cfg,
    )
    message["runtime"] = "live3d"
    message["live"] = resolve_live_config(directive, runtime_cfg=runtime_cfg)
    return message


def resolve_live_config(
    directive: AvatarDirective,
    *,
    runtime_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve the per-driver live-config block.

    Values come from ``runtime_cfg`` with sensible defaults. The
    projector accepts unknown values and falls back to safe defaults
    rather than raising — the frontend is free to add new strings
    without a contracts-level coordination dance.
    """
    cfg = dict(runtime_cfg or {})

    mouth_driver = _validate(cfg.get("mouth_driver"), _VALID_MOUTH_DRIVERS, default="amplitude")
    gaze_driver = _validate(cfg.get("gaze_driver"), _VALID_GAZE_DRIVERS, default="smooth")
    procedural_idle = _coerce_bool(cfg.get("procedural_idle"), default=True)
    blend_window_ms = _coerce_int(
        cfg.get("blend_window_ms"), default=DEFAULT_BLEND_WINDOW_MS, lo=0, hi=10_000
    )
    intensity = _clamp01(
        directive.intensity if directive.intensity is not None else 1.0
    )

    block: dict[str, Any] = {
        "mouth_driver": mouth_driver,
        "gaze_driver": gaze_driver,
        "procedural_idle": procedural_idle,
        "blend_window_ms": blend_window_ms,
        "intensity": intensity,
    }

    # Optional driver-specific extras.
    if mouth_driver == "amplitude":
        block["amplitude"] = _amplitude_block(cfg)
    elif mouth_driver == "viseme":
        block["viseme"] = _viseme_block(cfg)

    if procedural_idle:
        block["idle"] = _idle_block(cfg)

    if directive.gaze:
        block["gaze_target"] = directive.gaze

    return block


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _amplitude_block(cfg: dict[str, Any]) -> dict[str, Any]:
    raw = cfg.get("amplitude") if isinstance(cfg.get("amplitude"), dict) else {}
    return {
        "smoothing_ms": _coerce_int(raw.get("smoothing_ms"), default=80, lo=0, hi=2000),
        "gain": _coerce_float(raw.get("gain"), default=1.0, lo=0.0, hi=10.0),
        "open_curve": _clamp01(_coerce_float(raw.get("open_curve"), default=1.0, lo=0.0, hi=4.0)),
    }


def _viseme_block(cfg: dict[str, Any]) -> dict[str, Any]:
    raw = cfg.get("viseme") if isinstance(cfg.get("viseme"), dict) else {}
    return {
        "smoothing_ms": _coerce_int(raw.get("smoothing_ms"), default=60, lo=0, hi=2000),
        "default": str(raw.get("default") or "neutral"),
    }


def _idle_block(cfg: dict[str, Any]) -> dict[str, Any]:
    raw = cfg.get("idle") if isinstance(cfg.get("idle"), dict) else {}
    return {
        "breathing_amplitude": _clamp01(
            _coerce_float(raw.get("breathing_amplitude"), default=0.02, lo=0.0, hi=0.5)
        ),
        "breathing_period_ms": _coerce_int(
            raw.get("breathing_period_ms"), default=4200, lo=500, hi=20_000
        ),
        "saccade_min_ms": _coerce_int(
            raw.get("saccade_min_ms"), default=900, lo=100, hi=20_000
        ),
        "saccade_max_ms": _coerce_int(
            raw.get("saccade_max_ms"), default=2200, lo=100, hi=20_000
        ),
    }


def _validate(value: object, valid: frozenset[str], *, default: str) -> str:
    if isinstance(value, str) and value in valid:
        return value
    if value is not None:
        _log.debug("live3d projector: unknown %r; falling back to %r", value, default)
    return default


def _coerce_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in {"true", "1", "yes", "on"}:
            return True
        if value.lower() in {"false", "0", "no", "off"}:
            return False
    return default


def _coerce_int(value: object, *, default: int, lo: int, hi: int) -> int:
    try:
        out = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, out))


def _coerce_float(value: object, *, default: float, lo: float, hi: float) -> float:
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, out))


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)
