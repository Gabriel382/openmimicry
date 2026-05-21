"""Vision pipeline primitives — capture, throttle, detector registry.

The pipeline is composable: the adapter pulls frames out of
:class:`VideoCapture`, throttles to ``target_fps`` via
:class:`Throttle`, and runs the configured detectors (resolved
through :func:`load_detector`) before classifiers consume the result.

Heavy imports (``cv2``, ``mediapipe``, ``numpy``) live inside the
concrete detector modules under :mod:`.detectors` and inside
:mod:`.capture`. Importing this package is cheap.
"""

from __future__ import annotations

from .detectors import (
    DETECTOR_GROUP,
    DetectorUnavailable,
    available_detectors,
    load_detector,
)
from .throttle import Debouncer, Throttle

__all__ = [
    "DETECTOR_GROUP",
    "Debouncer",
    "DetectorUnavailable",
    "Throttle",
    "available_detectors",
    "load_detector",
]
