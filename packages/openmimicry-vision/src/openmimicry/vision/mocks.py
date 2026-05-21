"""Mock vision components — the canonical fixtures.

Imports here **must not** touch ``cv2`` or ``mediapipe`` at module
load time. That guarantees the unit suite + the M3 / M6 integration
tests can drive vision-shaped flows without any of the heavy deps
installed.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Sequence
from typing import Any

from openmimicry.core.contracts import (
    GestureClassifier,
    HandDetector,
    MovementClassifier,
    VisionAdapter,
)
from openmimicry.core.schemas import (
    GestureDetection,
    HandPose,
    MovementDetection,
    VisionConfig,
    VisionFrame,
)

__all__ = [
    "MockGestureClassifier",
    "MockHandDetector",
    "MockMovementClassifier",
    "MockVisionAdapter",
    "make_mock_gesture_classifier",
    "make_mock_hand_detector",
    "make_mock_movement_classifier",
    "make_mock_vision_adapter",
]


_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mock VisionAdapter
# ---------------------------------------------------------------------------


class MockVisionAdapter:
    """Programmable :class:`VisionAdapter`.

    Drive the async detection stream via :meth:`push_gesture` /
    :meth:`push_movement`. Frame snapshots can be staged via
    :meth:`push_frame`. Consent is granted by default so tests don't
    need to publish ``ConsentResolved`` themselves; pass
    ``require_consent=True`` on :meth:`start` to flip the gate back on.
    """

    name: str = "mock"

    def __init__(self) -> None:
        self.capabilities: set[str] = {"hands", "gestures", "movements"}
        self._detections: asyncio.Queue[GestureDetection | MovementDetection | None] = (
            asyncio.Queue()
        )
        self._frames: asyncio.Queue[VisionFrame | None] = asyncio.Queue()
        self._running: bool = False
        self._closed: bool = False
        self.config: VisionConfig | None = None
        # Tracking surfaces for tests.
        self.start_calls: int = 0
        self.stop_calls: int = 0
        self.gestures_pushed: list[GestureDetection] = []
        self.movements_pushed: list[MovementDetection] = []

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self, config: VisionConfig) -> None:
        self.config = config
        self.start_calls += 1
        self._running = True
        self._closed = False

    async def stop(self) -> None:
        self.stop_calls += 1
        self._running = False
        # Sentinel so pending iterators wake up and exit.
        await self._detections.put(None)
        await self._frames.put(None)

    @property
    def detections(self) -> AsyncIterator[GestureDetection | MovementDetection]:
        return self._iter_detections()

    async def _iter_detections(
        self,
    ) -> AsyncIterator[GestureDetection | MovementDetection]:
        while True:
            item = await self._detections.get()
            if item is None:
                return
            yield item

    @property
    def frames(self) -> AsyncIterator[VisionFrame]:
        return self._iter_frames()

    async def _iter_frames(self) -> AsyncIterator[VisionFrame]:
        while True:
            item = await self._frames.get()
            if item is None:
                return
            yield item

    async def healthcheck(self) -> bool:
        return not self._closed

    # ----- test-only hooks ---------------------------------------------------

    def push_gesture(
        self,
        name: str,
        *,
        hand: str = "right",
        confidence: float = 0.9,
        modality: str = "hand",
        source: str = "mock",
    ) -> None:
        det = GestureDetection(
            name=name,
            modality=modality,  # type: ignore[arg-type]
            hand=hand,  # type: ignore[arg-type]
            confidence=confidence,
            source=source,
        )
        self.gestures_pushed.append(det)
        self._detections.put_nowait(det)

    def push_movement(
        self,
        name: str,
        *,
        modality: str = "hand",
        hand: str | None = None,
        confidence: float = 0.9,
        duration_ms: int = 500,
        source: str = "mock",
    ) -> None:
        mov = MovementDetection(
            name=name,
            modality=modality,  # type: ignore[arg-type]
            hand=hand,  # type: ignore[arg-type]
            confidence=confidence,
            duration_ms=duration_ms,
            source=source,
        )
        self.movements_pushed.append(mov)
        self._detections.put_nowait(mov)

    def push_frame(self, frame: VisionFrame) -> None:
        self._frames.put_nowait(frame)


def make_mock_vision_adapter(*_args: Any, **_kwargs: Any) -> MockVisionAdapter:
    """Entry-point factory."""
    return MockVisionAdapter()


# ---------------------------------------------------------------------------
# Mock HandDetector — emits scripted HandPoses for the pipeline tests.
# ---------------------------------------------------------------------------


class MockHandDetector:
    """Returns a scripted ``list[HandPose]`` regardless of input."""

    name: str = "mock_hands"
    modality: str = "hand"

    def __init__(self, *, scripted: list[list[HandPose]] | None = None) -> None:
        self._scripted: list[list[HandPose]] = list(scripted or [])
        self._cursor: int = 0
        self._ready: bool = False
        self.detect_calls: int = 0

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def warmup(self) -> None:
        self._ready = True

    async def shutdown(self) -> None:
        self._ready = False

    async def detect(self, _frame_bgr: object) -> list[HandPose]:
        self.detect_calls += 1
        if not self._scripted:
            return []
        idx = min(self._cursor, len(self._scripted) - 1)
        self._cursor += 1
        return list(self._scripted[idx])

    # ----- test-only ---------------------------------------------------------

    def queue(self, poses: list[HandPose]) -> None:
        self._scripted.append(list(poses))


def make_mock_hand_detector(*_args: Any, **_kwargs: Any) -> MockHandDetector:
    return MockHandDetector()


# ---------------------------------------------------------------------------
# Mock classifiers
# ---------------------------------------------------------------------------


class MockGestureClassifier:
    """Returns a scripted sequence regardless of input."""

    name: str = "mock"

    def __init__(self, *, script: list[GestureDetection] | None = None) -> None:
        self._script: list[GestureDetection] = list(script or [])
        self._cursor: int = 0
        self.classify_calls: int = 0

    def classify(self, _pose: HandPose) -> GestureDetection | None:
        self.classify_calls += 1
        if not self._script:
            return None
        idx = min(self._cursor, len(self._script) - 1)
        self._cursor += 1
        return self._script[idx]


def make_mock_gesture_classifier(*_args: Any, **_kwargs: Any) -> MockGestureClassifier:
    return MockGestureClassifier()


class MockMovementClassifier:
    """Returns a scripted sequence regardless of input."""

    name: str = "mock"

    def __init__(self, *, script: list[MovementDetection] | None = None) -> None:
        self._script: list[MovementDetection] = list(script or [])
        self._cursor: int = 0
        self.classify_calls: int = 0

    def classify(self, _window: Sequence[VisionFrame]) -> MovementDetection | None:
        self.classify_calls += 1
        if not self._script:
            return None
        idx = min(self._cursor, len(self._script) - 1)
        self._cursor += 1
        return self._script[idx]


def make_mock_movement_classifier(*_args: Any, **_kwargs: Any) -> MockMovementClassifier:
    return MockMovementClassifier()


# ---------------------------------------------------------------------------
# Protocol assertions — fail loudly if a refactor breaks the surface.
# ---------------------------------------------------------------------------


def _protocol_self_check() -> None:
    """Asserts (at import time) every mock satisfies the Protocol it
    claims to satisfy. Kept private to avoid running on every import."""
    assert isinstance(MockVisionAdapter(), VisionAdapter)
    assert isinstance(MockHandDetector(), HandDetector)
    assert isinstance(MockGestureClassifier(), GestureClassifier)
    assert isinstance(MockMovementClassifier(), MovementClassifier)


# Optional: enable for local sanity by setting OPENMIMICRY_DEBUG=1.
# Off by default so the import cost stays trivial.
import os as _os  # noqa: E402

if _os.environ.get("OPENMIMICRY_DEBUG") == "1":
    _protocol_self_check()
