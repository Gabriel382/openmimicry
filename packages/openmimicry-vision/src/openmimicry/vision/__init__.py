"""openmimicry-vision: optional, opt-in webcam → hand/body/head detection (M13).

This package never opens a camera until ``VisionConfig.enabled`` is
``True`` AND consent has been granted on the bus
(see ``docs/modules/M13_vision.md`` §"Privacy and consent posture").

Public surface:

* :class:`MockVisionAdapter`, :class:`MockGestureClassifier`,
  :class:`MockMovementClassifier`, :class:`MockHandDetector` — all
  importable with **no** OpenCV / MediaPipe dependency.
* :class:`MediaPipeVisionAdapter` — composes detectors + classifiers
  + the bus. Lazy-imports heavy deps.
* The director-mapping helper translates ``GestureDetected`` /
  ``MovementDetected`` events to ``AvatarDirective`` overrides via
  the ``gesture_map`` / ``movement_map`` configured on
  ``VisionConfig``.

Detector and classifier registries (entry-point groups
``openmimicry.contracts.vision_detector`` /
``openmimicry.contracts.vision_gesture_classifier`` /
``openmimicry.contracts.vision_movement_classifier``) let third
parties plug in new modalities without touching this package.
"""

from __future__ import annotations

from .adapters.mediapipe_adapter import (
    MediaPipeVisionAdapter,
    MediaPipeVisionUnavailable,
    make_mediapipe_vision_adapter,
)
from .director_mapping import (
    apply_gesture_override,
    apply_movement_override,
    directive_from_gesture,
    directive_from_movement,
)
from .mocks import (
    MockGestureClassifier,
    MockHandDetector,
    MockMovementClassifier,
    MockVisionAdapter,
)

__all__ = [
    "MediaPipeVisionAdapter",
    "MediaPipeVisionUnavailable",
    "MockGestureClassifier",
    "MockHandDetector",
    "MockMovementClassifier",
    "MockVisionAdapter",
    "apply_gesture_override",
    "apply_movement_override",
    "directive_from_gesture",
    "directive_from_movement",
    "make_mediapipe_vision_adapter",
]

__version__ = "0.2.0a0"
