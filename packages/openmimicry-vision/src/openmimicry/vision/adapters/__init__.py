"""Vision adapters.

Currently:

* :class:`MediaPipeVisionAdapter` — webcam + MediaPipe detectors +
  classifier registry. Lazy imports.
* (mocks live in :mod:`openmimicry.vision.mocks`)
"""

from __future__ import annotations

from .mediapipe_adapter import (
    MediaPipeVisionAdapter,
    MediaPipeVisionUnavailable,
    make_mediapipe_vision_adapter,
)

__all__ = [
    "MediaPipeVisionAdapter",
    "MediaPipeVisionUnavailable",
    "make_mediapipe_vision_adapter",
]
