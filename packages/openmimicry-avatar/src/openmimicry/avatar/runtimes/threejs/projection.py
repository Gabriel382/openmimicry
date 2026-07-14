"""``build_threejs_projection`` — turn an ``AvatarDirective`` into a wire-message.

Output shape (additive extension of ``docs/contracts.md`` §9)::

    {
        "type": "avatar.directive",
        "runtime": "threejs",
        "directive": { /* AvatarDirective fields */ },
        "asset": { "kind": "vrm" | "gltf", "url": "...", "pack_id": "..." },
        "clip": "happy_speaking",
        "fallbackClips": ["happy_speaking", "happy", "idle"],
        "blendWeights": { "talk": 0.8, "happy": 0.6 },
        "expression": "happy",
        "expressionWeights": { "happy": 0.6 },
        "gestureClip": "wave",          // omitted when no gesture
        "gazeTarget": "towards_user",
        "intensity": 0.7,               // clamped to [0, 1]
        "fadeMs": 220
    }

The projector is pure. It never reads from disk and never raises on
unknown fields — the frontend is expected to ignore anything it doesn't
support (same rule as Sprite2D).
"""

from __future__ import annotations

import logging
from typing import Any

from openmimicry.core.schemas import AvatarDirective, CharacterPack, Emotion, State

__all__ = [
    "DEFAULT_FADE_MS",
    "build_threejs_projection",
    "clip_fallback_chain",
    "expression_weights",
    "pick_clip",
    "resolve_asset",
]


_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_FADE_MS: int = 220

# Per-emotion expression weight table. Mirrors the frontend's
# `expressions.ts` map; the two are tested against each other indirectly
# via the wire schema. Unknown emotions return an empty table — the
# frontend leaves the previous weights in place.
_EMOTION_WEIGHTS: dict[Emotion, dict[str, float]] = {
    "neutral": {},
    "happy": {"happy": 1.0},
    "sad": {"sad": 1.0, "neutral": 0.3},
    "angry": {"angry": 1.0},
    "confused": {"surprised": 0.6, "neutral": 0.3},
    "focused": {"neutral": 0.3, "happy": 0.1},
    "worried": {"sad": 0.6, "angry": 0.2},
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def build_threejs_projection(
    directive: AvatarDirective,
    pack: CharacterPack,
    *,
    static_url_prefix: str = "/static/characters",
    runtime_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the Three.js wire message for ``directive`` against ``pack``."""
    runtime_cfg = dict(runtime_cfg or {})
    asset = resolve_asset(pack, runtime_cfg=runtime_cfg, static_url_prefix=static_url_prefix)

    chain = clip_fallback_chain(directive.state, directive.emotion, directive.speaking)
    clip = pick_clip(chain, available=runtime_cfg.get("clips"))

    intensity = _clamp01(directive.intensity if directive.intensity is not None else 1.0)
    weights = expression_weights(directive.emotion, intensity=intensity)

    blend_weights = _blend_weights(directive=directive, intensity=intensity)

    message: dict[str, Any] = {
        "type": "avatar.directive",
        "runtime": "threejs",
        "directive": directive.model_dump(mode="json"),
        "asset": asset,
        "clip": clip,
        "fallbackClips": chain,
        "blendWeights": blend_weights,
        "expression": directive.emotion,
        "expressionWeights": weights,
        "intensity": intensity,
        "gazeTarget": directive.gaze or runtime_cfg.get("default_gaze") or "towards_user",
        "fadeMs": int(runtime_cfg.get("fade_ms", DEFAULT_FADE_MS)),
    }

    if directive.gesture:
        gesture_clip = _gesture_clip(directive.gesture, runtime_cfg=runtime_cfg)
        if gesture_clip is not None:
            message["gestureClip"] = gesture_clip
        else:
            _log.debug("threejs projection: unknown gesture %r; dropping", directive.gesture)

    return message


def clip_fallback_chain(
    state: State, emotion: Emotion, speaking: bool
) -> list[str]:
    """Return the ordered list of clip names to try.

    Convention (mirrors ``docs/character_packs.md`` §4): the frontend
    plays the first available clip and falls through to the next on
    miss. Always ends with ``"idle"`` so the renderer always has
    something to do.
    """
    chain: list[str] = []
    if speaking:
        chain.append(f"{emotion}_{state}_speaking")
        chain.append(f"{state}_speaking")
    chain.append(f"{emotion}_{state}")
    chain.append(state)
    if "idle" not in chain:
        chain.append("idle")
    # Stable de-duplication preserving first occurrence.
    seen: set[str] = set()
    out: list[str] = []
    for name in chain:
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def pick_clip(chain: list[str], *, available: list[str] | None) -> str:
    """Pick the first clip in ``chain`` that exists in ``available``.

    When ``available`` is ``None`` (the common case — packs ship without
    an explicit clip manifest), the first entry of the chain is
    returned. The frontend is then responsible for its own fallback.
    """
    if not chain:
        return "idle"
    if available is None:
        return chain[0]
    available_set = {str(name) for name in available}
    for name in chain:
        if name in available_set:
            return name
    # No clip in the chain matched the manifest. The frontend will play
    # whatever default the loader produces, but we return "idle" so the
    # field is never empty.
    return "idle"


def expression_weights(emotion: Emotion, *, intensity: float) -> dict[str, float]:
    """Return scaled VRM expression weights for ``emotion``.

    ``intensity`` is multiplied into every weight. The returned dict is
    a fresh copy on every call so the caller can mutate without leaking
    into the table.
    """
    base = _EMOTION_WEIGHTS.get(emotion, {})
    scaled: dict[str, float] = {}
    for key, value in base.items():
        scaled[key] = _clamp01(value * intensity)
    return scaled


def resolve_asset(
    pack: CharacterPack,
    *,
    runtime_cfg: dict[str, Any],
    static_url_prefix: str,
) -> dict[str, Any]:
    """Return the asset descriptor (`kind` + `url` + `pack_id`).

    Resolution order:

    1. Explicit ``runtime_cfg.asset`` (e.g. ``{"kind": "vrm", "path": "x.vrm"}``).
    2. ``pack.metadata.asset`` if present.
    3. Convention: ``{static_url_prefix}/{pack.id}/character.{kind}``.

    ``kind`` defaults to ``"vrm"`` when the pack declares
    ``kind == "vrm"``; otherwise it's ``"gltf"`` (covers gltf, glb, and
    advanced2d-ish fallbacks for completeness).
    """
    explicit = runtime_cfg.get("asset")
    if isinstance(explicit, dict) and explicit.get("url"):
        return {
            "kind": str(explicit.get("kind") or _default_kind(pack)),
            "url": str(explicit["url"]),
            "pack_id": pack.id,
        }

    metadata_asset = pack.metadata.get("asset") if pack.metadata else None
    if isinstance(metadata_asset, dict) and metadata_asset.get("path"):
        path = str(metadata_asset["path"])
        return {
            "kind": str(metadata_asset.get("kind") or _default_kind(pack)),
            "url": _to_static_url(path, pack.id, static_url_prefix),
            "pack_id": pack.id,
        }

    kind = _default_kind(pack)
    return {
        "kind": kind,
        "url": f"{static_url_prefix.rstrip('/')}/{pack.id}/character.{kind}",
        "pack_id": pack.id,
    }


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _default_kind(pack: CharacterPack) -> str:
    if pack.kind == "vrm":
        return "vrm"
    if pack.kind in {"gltf", "threejs"}:
        return "gltf"
    # Any other pack.kind (sprite2d, advanced2d, …) being routed through
    # the Three.js adapter is a misconfiguration — but we don't raise
    # because the projector is pure. Default to gltf so the URL is
    # well-formed; the adapter logs the misuse separately.
    return "gltf"


def _to_static_url(path: str, pack_id: str, static_url_prefix: str) -> str:
    cleaned = path.strip()
    if cleaned.startswith(("http://", "https://", "/")):
        return cleaned
    return f"{static_url_prefix.rstrip('/')}/{pack_id}/{cleaned.lstrip('./')}"


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def _blend_weights(*, directive: AvatarDirective, intensity: float) -> dict[str, float]:
    """Coarse blend-weight hints for the renderer.

    The frontend mixes these with the expression weights and the current
    clip. They're intentionally small — the heavy lifting is in
    ``expressionWeights``.
    """
    weights: dict[str, float] = {}
    if directive.speaking:
        weights["talk"] = _clamp01(0.6 + 0.4 * intensity)
    if directive.emotion in {"happy", "neutral", "focused"}:
        # Subtle base smile/neutral overlay so the avatar doesn't look
        # frozen between clips.
        weights.setdefault(directive.emotion, _clamp01(0.2 + 0.4 * intensity))
    if directive.state == "thinking":
        weights["think"] = _clamp01(0.4 + 0.4 * intensity)
    return weights


def _gesture_clip(gesture: str, *, runtime_cfg: dict[str, Any]) -> str | None:
    """Map ``directive.gesture`` to a clip name.

    Resolution order: ``runtime_cfg.gestures[gesture]`` (per-pack map) →
    the raw gesture string itself (acceptable since clip names are
    free-form). Unknown gestures return ``None`` and the projection
    omits the field.
    """
    gestures = runtime_cfg.get("gestures")
    if isinstance(gestures, dict):
        mapped = gestures.get(gesture)
        if isinstance(mapped, str) and mapped:
            return mapped
    # Allowlist of well-known gestures so a typo doesn't smuggle in an
    # unintended clip name. The set is intentionally short; packs add
    # their own through `runtime_cfg.gestures`.
    known = {"wave", "nod", "shake", "shrug", "point", "thumbs_up", "thumbs_down"}
    if gesture in known:
        return gesture
    return None
