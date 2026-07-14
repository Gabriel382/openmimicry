"""MockVisionAdapter + mock classifiers — Protocol satisfaction + flow."""

from __future__ import annotations

import asyncio

from openmimicry.core.contracts import (
    GestureClassifier,
    HandDetector,
    MovementClassifier,
    VisionAdapter,
)
from openmimicry.core.schemas import GestureDetection, VisionConfig
from openmimicry.vision.mocks import (
    MockGestureClassifier,
    MockHandDetector,
    MockMovementClassifier,
    MockVisionAdapter,
)


def test_protocol_satisfaction() -> None:
    assert isinstance(MockVisionAdapter(), VisionAdapter)
    assert isinstance(MockHandDetector(), HandDetector)
    assert isinstance(MockGestureClassifier(), GestureClassifier)
    assert isinstance(MockMovementClassifier(), MovementClassifier)


async def test_mock_vision_adapter_start_stop_lifecycle() -> None:
    adapter = MockVisionAdapter()
    await adapter.start(VisionConfig(enabled=True))
    assert adapter.is_running is True
    assert adapter.start_calls == 1
    await adapter.stop()
    assert adapter.is_running is False
    assert adapter.stop_calls == 1


async def test_push_gesture_appears_on_stream() -> None:
    adapter = MockVisionAdapter()
    await adapter.start(VisionConfig(enabled=True))
    adapter.push_gesture("wave", confidence=0.9)

    async def _collect() -> list:
        out: list = []
        async for det in adapter.detections:
            out.append(det)
            if len(out) >= 1:
                await adapter.stop()
        return out

    received = await asyncio.wait_for(_collect(), timeout=1.0)
    assert received[0].name == "wave"
    assert received[0].source == "mock"


async def test_push_movement_appears_on_stream() -> None:
    adapter = MockVisionAdapter()
    await adapter.start(VisionConfig(enabled=True))
    adapter.push_movement("nodding", modality="head", confidence=0.9)

    async def _collect() -> list:
        out: list = []
        async for det in adapter.detections:
            out.append(det)
            if len(out) >= 1:
                await adapter.stop()
        return out

    received = await asyncio.wait_for(_collect(), timeout=1.0)
    assert received[0].name == "nodding"
    assert received[0].modality == "head"


def test_mock_gesture_classifier_scripted_sequence() -> None:
    from openmimicry.core.schemas import HandPose, Landmark

    script = [
        GestureDetection(name="wave", modality="hand", hand="right", confidence=0.9),
        GestureDetection(name="thumbs_up", modality="hand", hand="right", confidence=0.9),
    ]
    cls = MockGestureClassifier(script=script)
    pose = HandPose(hand="right", landmarks=[Landmark(x=0, y=0)] * 21, confidence=1.0)
    out = [cls.classify(pose), cls.classify(pose)]
    assert [d.name for d in out if d] == ["wave", "thumbs_up"]


def test_mocks_module_never_imports_cv2_or_mediapipe() -> None:
    """The mocks module must work without OpenCV / MediaPipe."""
    import sys

    mocks = sys.modules.get("openmimicry.vision.mocks")
    assert mocks is not None
    # No accidental leak from inside the module.
    src = mocks.__file__
    assert src is not None
    with open(src, encoding="utf-8") as f:
        text = f.read()
    assert "import cv2" not in text
    assert "import mediapipe" not in text
