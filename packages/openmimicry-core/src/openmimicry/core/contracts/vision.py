"""Frozen Protocols for the vision subsystem (M13).

Three plug points:

* :class:`VisionAdapter` — the top-level adapter. M13 ships
  ``MockVisionAdapter`` + ``MediaPipeVisionAdapter``; future modules
  ship their own.
* :class:`LandmarkDetector` — sub-component the adapter composes. A
  ``HandDetector`` / ``BodyDetector`` / ``HeadDetector`` all satisfy
  this Protocol so M14+ can ship a new detector without amending the
  adapter.
* :class:`GestureClassifier` and :class:`MovementClassifier` —
  pure-function classifiers consuming poses or movement windows.

The classifier surface is deliberately small (one classify call,
optional warm-up). Implementations may be rule-based, sklearn, ONNX,
TF-Lite, or third-party.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Protocol, runtime_checkable

from ..schemas.vision import (
    BodyPose,
    GestureDetection,
    HandPose,
    HeadPose,
    MovementDetection,
    VisionConfig,
    VisionFrame,
)

__all__ = [
    "BodyDetector",
    "GestureClassifier",
    "HandDetector",
    "HeadDetector",
    "LandmarkDetector",
    "MovementClassifier",
    "VisionAdapter",
]


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


@runtime_checkable
class VisionAdapter(Protocol):
    """Top-level adapter — opens the camera + runs the pipeline.

    Drives a stream of :class:`GestureDetection` / :class:`MovementDetection`
    via the :attr:`detections` property. Implementations also publish
    snapshot :class:`VisionFrame` updates so other consumers (panel UI,
    director) can react to raw landmarks if they want.
    """

    name: str
    capabilities: set[str]
    """e.g. ``{"hands", "gestures"}``; future ``{"body", "head"}``."""

    async def start(self, config: VisionConfig) -> None: ...

    async def stop(self) -> None: ...

    @property
    def detections(self) -> AsyncIterator[GestureDetection | MovementDetection]: ...

    @property
    def frames(self) -> AsyncIterator[VisionFrame]: ...

    @property
    def is_running(self) -> bool: ...

    async def healthcheck(self) -> bool: ...


# ---------------------------------------------------------------------------
# Pluggable detector micro-Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LandmarkDetector(Protocol):
    """One sub-detector inside the adapter.

    Detectors are stateless across frames from the adapter's
    perspective — they consume a single BGR frame and return whatever
    they found. Stateful smoothing (e.g. MediaPipe's internal tracker)
    lives inside the implementation.
    """

    name: str
    """e.g. ``"mediapipe_hands"``, ``"mediapipe_pose"``."""

    modality: str
    """``"hand"`` / ``"body"`` / ``"head"`` — used by the registry to
    bind the detector to the right ``vision.detectors.<modality>``
    config block."""

    async def warmup(self) -> None: ...
    """Allocate the underlying model. Called once on ``start()``."""

    async def shutdown(self) -> None: ...

    async def detect(self, frame_bgr: object) -> object: ...
    """Run one detection. ``frame_bgr`` is an ``ndarray`` (HxWx3, BGR);
    the return type is modality-specific. The adapter knows how to
    unpack it because it bound the detector to the right modality at
    registration time."""

    @property
    def is_ready(self) -> bool: ...


@runtime_checkable
class HandDetector(LandmarkDetector, Protocol):
    """Specialisation: returns ``list[HandPose]``."""

    async def detect(self, frame_bgr: object) -> list[HandPose]: ...


@runtime_checkable
class BodyDetector(LandmarkDetector, Protocol):
    """Specialisation: returns ``BodyPose | None``."""

    async def detect(self, frame_bgr: object) -> BodyPose | None: ...


@runtime_checkable
class HeadDetector(LandmarkDetector, Protocol):
    """Specialisation: returns ``HeadPose | None``."""

    async def detect(self, frame_bgr: object) -> HeadPose | None: ...


# ---------------------------------------------------------------------------
# Classifier Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class GestureClassifier(Protocol):
    """Pure-function classifier — 21-point pose → gesture name.

    Implementations may be rule-based, scikit-learn, ONNX, TF-Lite.
    The adapter doesn't care which.
    """

    name: str

    def classify(self, pose: HandPose) -> GestureDetection | None: ...


@runtime_checkable
class MovementClassifier(Protocol):
    """Temporal classifier — recent pose window → movement name.

    The adapter feeds a short ring buffer of recent
    :class:`VisionFrame`s; classifier picks one (or none) of its
    movements.
    """

    name: str

    def classify(self, window: Sequence[VisionFrame]) -> MovementDetection | None: ...
