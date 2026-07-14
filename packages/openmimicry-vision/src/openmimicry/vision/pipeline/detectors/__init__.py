"""Detector registry — entry-point group ``openmimicry.contracts.vision_detector``.

Each registered factory takes ``**kwargs`` (forwarded from
``VisionDetectorConfig.extra``) and returns a
:class:`LandmarkDetector`. The adapter looks up detectors by name
so new modalities (face, body-tracking, third-party) plug in
without amending this package.
"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points
from typing import Any

__all__ = [
    "DETECTOR_GROUP",
    "DetectorUnavailable",
    "available_detectors",
    "load_detector",
]


_log = logging.getLogger(__name__)


DETECTOR_GROUP = "openmimicry.contracts.vision_detector"


class DetectorUnavailable(RuntimeError):
    """Raised when a detector factory can't satisfy its dependencies
    (e.g. ``mediapipe`` missing). Callers treat it as a hard skip
    rather than a crash."""


def available_detectors() -> list[str]:
    """Return the names of every registered detector entry point."""
    try:
        eps = entry_points(group=DETECTOR_GROUP)
    except TypeError:
        # Older importlib.metadata API.
        eps = entry_points().get(DETECTOR_GROUP, [])  # type: ignore[attr-defined]
    return sorted(ep.name for ep in eps)


def load_detector(name: str, **kwargs: Any) -> Any:
    """Look up + instantiate the detector named ``name``.

    Returns the detector instance. Raises :class:`DetectorUnavailable`
    when the entry point isn't installed or its factory fails.
    """
    try:
        eps = entry_points(group=DETECTOR_GROUP)
    except TypeError:
        eps = entry_points().get(DETECTOR_GROUP, [])  # type: ignore[attr-defined]

    match: Any = None
    for ep in eps:
        if ep.name == name:
            match = ep
            break
    if match is None:
        raise DetectorUnavailable(
            f"vision detector {name!r} not registered (available: {available_detectors()})"
        )
    try:
        factory = match.load()
    except Exception as exc:
        raise DetectorUnavailable(f"vision detector {name!r} failed to load: {exc}") from exc
    return factory(**kwargs)
