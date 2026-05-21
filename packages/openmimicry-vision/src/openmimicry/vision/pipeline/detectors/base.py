"""Shared helpers + the lazy MediaPipe import."""

from __future__ import annotations

import logging
from typing import Any

__all__ = ["MediaPipeUnavailable", "import_mediapipe"]


_log = logging.getLogger(__name__)


class MediaPipeUnavailable(RuntimeError):
    """Raised when ``mediapipe`` is not importable."""


def import_mediapipe() -> Any:
    """Lazy-import ``mediapipe`` with a typed error.

    Cached on the module so repeated calls are cheap.
    """
    try:
        import mediapipe  # type: ignore[import-not-found]
    except ImportError as exc:
        raise MediaPipeUnavailable(
            "mediapipe is not installed. Install with "
            '`pip install "openmimicry-vision[mediapipe]"`.'
        ) from exc
    return mediapipe
