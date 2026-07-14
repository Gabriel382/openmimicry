"""Director mapping — gesture/movement → AvatarDirective override."""

from __future__ import annotations

from openmimicry.core.schemas import GestureDetection, MovementDetection
from openmimicry.vision.director_mapping import (
    directive_from_gesture,
    directive_from_movement,
)


def test_wave_gesture_maps_to_directive() -> None:
    gesture_map = {
        "wave": {"emotion": "happy", "gesture": "wave", "duration_ms": 1200},
    }
    det = GestureDetection(name="wave", modality="hand", hand="right", confidence=0.9)
    directive = directive_from_gesture(det, gesture_map)
    assert directive is not None
    assert directive.emotion == "happy"
    assert directive.gesture == "wave"
    assert directive.duration_ms == 1200
    # Defaults applied + provenance recorded.
    assert directive.state == "happy"
    assert directive.metadata["vision_source"] == "vision_gesture:wave"
    assert directive.metadata["vision_confidence"] == 0.9


def test_unmapped_gesture_returns_none() -> None:
    gesture_map = {"wave": {"emotion": "happy"}}
    det = GestureDetection(name="not-a-gesture", modality="hand", hand="right", confidence=0.9)
    assert directive_from_gesture(det, gesture_map) is None


def test_unknown_keys_in_override_are_dropped() -> None:
    gesture_map = {
        "wave": {"emotion": "happy", "garbage_field": "x", "duration_ms": 1200},
    }
    det = GestureDetection(name="wave", modality="hand", hand="right", confidence=0.9)
    directive = directive_from_gesture(det, gesture_map)
    assert directive is not None
    # garbage_field was dropped.
    assert not hasattr(directive, "garbage_field")
    assert directive.emotion == "happy"


def test_movement_maps_to_directive_with_duration_fallback() -> None:
    movement_map = {"nodding": {"state": "happy", "emotion": "happy"}}
    det = MovementDetection(name="nodding", modality="head", confidence=0.8, duration_ms=600)
    directive = directive_from_movement(det, movement_map)
    assert directive is not None
    assert directive.state == "happy"
    # The override didn't supply a duration; the detection's
    # duration_ms fills in as a fallback.
    assert directive.duration_ms == 600


def test_state_default_when_not_supplied() -> None:
    gesture_map = {"wave": {"emotion": "happy"}}
    det = GestureDetection(name="wave", modality="hand", hand="right", confidence=0.9)
    directive = directive_from_gesture(det, gesture_map)
    assert directive is not None
    assert directive.state == "happy"
