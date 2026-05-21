"""``MediaPipeVisionAdapter`` driven with a fake VideoCapture + detectors.

This test deliberately *does not* import OpenCV or MediaPipe. The
adapter accepts an injected ``capture`` and uses ``load_detector``
+ ``load_gesture_classifier`` from entry points; we register
custom factories at runtime via ``setattr`` on the registry helpers.
"""

from __future__ import annotations

import asyncio
import logging

import pytest
from openmimicry.core.schemas import (
    GestureDetection,
    HandPose,
    Landmark,
    VisionClassifierConfig,
    VisionConfig,
    VisionDetectorConfig,
)
from openmimicry.vision.adapters import MediaPipeVisionAdapter, MediaPipeVisionUnavailable
from openmimicry.vision.classifiers import base as cls_base
from openmimicry.vision.pipeline import detectors as det_reg
from openmimicry.vision.pipeline.capture import VideoCapture


class _FakeVideoCapture(VideoCapture):
    """In-process capture — pushes synthetic frames into the queue."""

    def __init__(self, frames: list[object]) -> None:
        super().__init__(camera_index=0, target_fps=60, queue_size=8)
        self._synthetic = list(frames)

    async def start(self) -> None:  # type: ignore[override]
        # Skip cv2 entirely; just seed the queue.
        for frame in self._synthetic:
            await self.frames.put(frame)
        await self.frames.put(None)
        self._running.set()

    async def stop(self) -> None:  # type: ignore[override]
        self._running.clear()


class _FakeFrame:
    shape = (480, 640, 3)


class _FakeHandsDetector:
    name = "fake_hands"
    modality = "hand"

    def __init__(self, *, poses: list[list[HandPose]]) -> None:
        self._poses = list(poses)
        self._cursor = 0
        self._ready = False

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def warmup(self) -> None:
        self._ready = True

    async def shutdown(self) -> None:
        self._ready = False

    async def detect(self, _frame_bgr: object) -> list[HandPose]:
        idx = min(self._cursor, len(self._poses) - 1)
        self._cursor += 1
        return list(self._poses[idx])


def _open_palm() -> HandPose:
    # 21-point landmark fixture — open palm matches the rule classifier.
    landmarks = [Landmark(x=0.5, y=0.8)]  # wrist
    landmarks += [
        Landmark(x=0.45, y=0.78), Landmark(x=0.4, y=0.74),
        Landmark(x=0.34, y=0.72), Landmark(x=0.28, y=0.70),  # thumb
    ]
    for x in (0.46, 0.50, 0.54, 0.58):
        landmarks += [
            Landmark(x=x, y=0.7), Landmark(x=x, y=0.66),
            Landmark(x=x, y=0.62), Landmark(x=x, y=0.58),
        ]
    return HandPose(hand="right", landmarks=landmarks, confidence=0.95)


@pytest.fixture(autouse=True)
def _register_fake_detector(monkeypatch: pytest.MonkeyPatch):
    """Wire a hand detector that doesn't touch MediaPipe."""
    poses = [[_open_palm()] for _ in range(8)]
    detector = _FakeHandsDetector(poses=poses)

    def _load_detector_stub(name: str, **_kw):
        if name == "mediapipe_hands":
            return detector
        from openmimicry.vision.pipeline.detectors import DetectorUnavailable

        raise DetectorUnavailable(f"unsupported in test: {name}")

    monkeypatch.setattr(det_reg, "load_detector", _load_detector_stub)
    # Also patch the symbol the adapter imported.
    import openmimicry.vision.adapters.mediapipe_adapter as mp_adapter

    monkeypatch.setattr(mp_adapter, "load_detector", _load_detector_stub)
    yield detector


@pytest.fixture(autouse=True)
def _register_rule_classifier(monkeypatch: pytest.MonkeyPatch):
    """Force gesture lookups to resolve the rule-based default and
    movement lookups to a no-op so the test stays deterministic."""
    from openmimicry.vision.classifiers.rules import RuleGestureClassifier

    def _load_gesture(name: str, **kw):
        return RuleGestureClassifier(**{k: v for k, v in kw.items() if k == "threshold"})

    class _NoopMovement:
        name = "noop"

        def classify(self, _window):
            return None

    def _load_movement(_name: str, **_kw):
        return _NoopMovement()

    monkeypatch.setattr(cls_base, "load_gesture_classifier", _load_gesture)
    monkeypatch.setattr(cls_base, "load_movement_classifier", _load_movement)

    import openmimicry.vision.adapters.mediapipe_adapter as mp_adapter

    monkeypatch.setattr(mp_adapter, "load_gesture_classifier", _load_gesture)
    monkeypatch.setattr(mp_adapter, "load_movement_classifier", _load_movement)


async def test_adapter_publishes_open_palm_detection() -> None:
    capture = _FakeVideoCapture(frames=[_FakeFrame() for _ in range(5)])
    adapter = MediaPipeVisionAdapter(capture=capture)
    cfg = VisionConfig(
        enabled=True,
        target_fps=60,
        require_consent=False,
        detectors={"hands": VisionDetectorConfig(enabled=True)},
    )

    await adapter.start(cfg)
    try:
        det = await asyncio.wait_for(_first_detection(adapter), timeout=1.0)
    finally:
        await adapter.stop()
    assert det.name == "open_palm"
    assert det.modality == "hand"


async def test_adapter_refuses_to_start_when_disabled() -> None:
    adapter = MediaPipeVisionAdapter()
    with pytest.raises(MediaPipeVisionUnavailable):
        await adapter.start(VisionConfig(enabled=False))


async def test_adapter_refuses_when_consent_resolver_returns_false(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
    capture = _FakeVideoCapture(frames=[])
    adapter = MediaPipeVisionAdapter(
        capture=capture,
        consent_resolver=lambda: False,
    )
    with pytest.raises(MediaPipeVisionUnavailable):
        await adapter.start(VisionConfig(enabled=True, require_consent=True))


async def test_adapter_emits_frames_with_landmark_data() -> None:
    capture = _FakeVideoCapture(frames=[_FakeFrame() for _ in range(3)])
    adapter = MediaPipeVisionAdapter(capture=capture)
    cfg = VisionConfig(
        enabled=True,
        target_fps=60,
        require_consent=False,
        detectors={"hands": VisionDetectorConfig(enabled=True)},
        # Disable gesture classifier so we just see frames.
        gesture_classifiers={
            "off": VisionClassifierConfig(kind="rules", enabled=False)
        },
        movement_classifiers={
            "off": VisionClassifierConfig(kind="rules", enabled=False)
        },
    )
    await adapter.start(cfg)
    try:
        frame = await asyncio.wait_for(_first_frame(adapter), timeout=1.0)
    finally:
        await adapter.stop()
    assert len(frame.hands) == 1
    assert len(frame.hands[0].landmarks) == 21


async def _first_detection(adapter):
    async for det in adapter.detections:
        return det
    raise RuntimeError("no detection")


async def _first_frame(adapter):
    async for f in adapter.frames:
        if f.hands:
            return f
    raise RuntimeError("no frame")
