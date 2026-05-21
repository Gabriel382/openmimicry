"""Map vision events to ``AvatarDirective`` overrides.

The mapping is configured via ``vision.gesture_map`` and
``vision.movement_map``:

```yaml
vision:
  gesture_map:
    wave:        { emotion: happy, gesture: wave,        duration_ms: 1200 }
    thumbs_up:   { emotion: happy, gesture: thumbs_up,   duration_ms: 800 }
    peace:       { emotion: happy, gesture: peace,       duration_ms: 800 }
  movement_map:
    wave_motion: { emotion: happy, gesture: wave,        duration_ms: 1500, intensity: 0.8 }
    nodding:     { state: happy,   emotion: happy,       duration_ms: 600 }
    shaking_head:{ state: error,   emotion: worried,     duration_ms: 600 }
```

The helpers are pure: caller subscribes to the bus, calls
``directive_from_gesture(detection, gesture_map)`` (or
``apply_gesture_override(...)`` which routes through the active
orchestrator) and applies whatever ``AvatarDirective`` comes back.
M3's director consumes the synthesised directives the same way as
any other event-driven directive — no contract amendment needed.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from openmimicry.core.schemas import (
    AvatarDirective,
    GestureDetection,
    MovementDetection,
)

__all__ = [
    "apply_gesture_override",
    "apply_movement_override",
    "directive_from_detection",
    "directive_from_gesture",
    "directive_from_movement",
]


_log = logging.getLogger(__name__)


# Whitelisted directive keys the gesture-map is allowed to override.
# Anything else is dropped with a single log; this stops gesture
# maps from sending arbitrary garbage into the AvatarDirective
# schema.
_ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "state",
        "emotion",
        "animation",
        "speaking",
        "text",
        "next_state",
        "duration_ms",
        "intensity",
        "gesture",
        "gaze",
        "metadata",
    }
)


def directive_from_gesture(
    detection: GestureDetection,
    gesture_map: Mapping[str, Mapping[str, Any]],
    *,
    base: AvatarDirective | None = None,
) -> AvatarDirective | None:
    """Resolve a ``GestureDetection`` into an :class:`AvatarDirective`.

    Returns ``None`` when the gesture isn't mapped. The detection's
    confidence is annotated under ``metadata.vision_confidence``.
    """
    override = gesture_map.get(detection.name)
    if not override:
        return None
    return _apply_override(
        override,
        base=base,
        source=f"vision_gesture:{detection.name}",
        confidence=detection.confidence,
    )


def directive_from_movement(
    detection: MovementDetection,
    movement_map: Mapping[str, Mapping[str, Any]],
    *,
    base: AvatarDirective | None = None,
) -> AvatarDirective | None:
    """Resolve a ``MovementDetection`` into an :class:`AvatarDirective`."""
    override = movement_map.get(detection.name)
    if not override:
        return None
    return _apply_override(
        override,
        base=base,
        source=f"vision_movement:{detection.name}",
        confidence=detection.confidence,
        duration_ms_fallback=detection.duration_ms,
    )


def directive_from_detection(
    detection: GestureDetection | MovementDetection,
    *,
    gesture_map: Mapping[str, Mapping[str, Any]],
    movement_map: Mapping[str, Mapping[str, Any]],
    base: AvatarDirective | None = None,
) -> AvatarDirective | None:
    """Dispatch convenience."""
    if isinstance(detection, GestureDetection):
        return directive_from_gesture(detection, gesture_map, base=base)
    return directive_from_movement(detection, movement_map, base=base)


# ---------------------------------------------------------------------------
# Wiring helpers — keep the import surface tiny
# ---------------------------------------------------------------------------


ApplyDirective = Callable[[AvatarDirective], Awaitable[None]]


async def apply_gesture_override(
    detection: GestureDetection,
    *,
    gesture_map: Mapping[str, Mapping[str, Any]],
    apply: ApplyDirective,
    base: AvatarDirective | None = None,
) -> AvatarDirective | None:
    """Look up the directive and forward it to ``apply``.

    Returns the directive that was applied (or ``None`` when the
    gesture isn't mapped).
    """
    directive = directive_from_gesture(detection, gesture_map, base=base)
    if directive is None:
        return None
    await apply(directive)
    return directive


async def apply_movement_override(
    detection: MovementDetection,
    *,
    movement_map: Mapping[str, Mapping[str, Any]],
    apply: ApplyDirective,
    base: AvatarDirective | None = None,
) -> AvatarDirective | None:
    directive = directive_from_movement(detection, movement_map, base=base)
    if directive is None:
        return None
    await apply(directive)
    return directive


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _apply_override(
    override: Mapping[str, Any],
    *,
    base: AvatarDirective | None,
    source: str,
    confidence: float,
    duration_ms_fallback: int | None = None,
) -> AvatarDirective:
    fields: dict[str, Any] = {}
    if base is not None:
        fields.update(base.model_dump(mode="python"))
    for key, value in override.items():
        if key not in _ALLOWED_KEYS:
            _log.debug("vision director_mapping: dropping unknown key %r", key)
            continue
        fields[key] = value
    if "duration_ms" not in fields and duration_ms_fallback:
        fields["duration_ms"] = duration_ms_fallback
    # Always set state to something valid; default to happy when an
    # override doesn't supply one (gestures usually celebrate).
    fields.setdefault("state", "happy")
    metadata = dict(fields.get("metadata") or {})
    metadata["vision_source"] = source
    metadata["vision_confidence"] = confidence
    fields["metadata"] = metadata
    return AvatarDirective.model_validate(fields)
