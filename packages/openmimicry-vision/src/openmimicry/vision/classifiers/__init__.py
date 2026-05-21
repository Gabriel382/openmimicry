"""Gesture-classifier registry.

Three default classifiers ship:

* :mod:`.rules` — pure-Python heuristic checks against the 21-point
  MediaPipe Hands skeleton. Default for the demo profile.
* :mod:`.sklearn` — joblib-loaded scikit-learn classifier. Lazy
  import.
* :mod:`.onnx` — onnxruntime classifier. Lazy import.

The runtime resolution path is the same entry-point pattern as the
detector registry, so third-party classifiers register themselves
without touching this package.
"""

from __future__ import annotations

from .base import (
    GESTURE_GROUP,
    MOVEMENT_GROUP,
    ClassifierUnavailable,
    available_gesture_classifiers,
    available_movement_classifiers,
    load_gesture_classifier,
    load_movement_classifier,
)

__all__ = [
    "ClassifierUnavailable",
    "GESTURE_GROUP",
    "MOVEMENT_GROUP",
    "available_gesture_classifiers",
    "available_movement_classifiers",
    "load_gesture_classifier",
    "load_movement_classifier",
]
