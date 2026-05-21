"""Temporal movement classifier — wave, nod, shake, raised hand."""

from __future__ import annotations

import math

from openmimicry.core.schemas import HandPose, HeadPose, Landmark, VisionFrame
from openmimicry.vision.classifiers.movements.rules import RuleMovementClassifier


def _frame_with_index_tip(*, ts_ms: int, tip_x: float) -> VisionFrame:
    landmarks = [Landmark(x=0.5, y=0.8)] + [Landmark(x=0.5, y=0.8)] * 7
    # Index TIP is landmark index 8 — make it x=tip_x.
    landmarks.append(Landmark(x=tip_x, y=0.5))
    landmarks += [Landmark(x=0.5, y=0.6)] * 12
    assert len(landmarks) == 21
    hand = HandPose(hand="right", landmarks=landmarks, confidence=0.9)
    return VisionFrame(ts_ms=ts_ms, hands=[hand])


def _frame_with_head(*, ts_ms: int, yaw: float = 0.0, pitch: float = 0.0) -> VisionFrame:
    return VisionFrame(ts_ms=ts_ms, head=HeadPose(yaw=yaw, pitch=pitch))


def test_wave_motion_detected_when_index_tip_oscillates() -> None:
    cls = RuleMovementClassifier(min_amplitude=0.05)
    window = [
        _frame_with_index_tip(ts_ms=0, tip_x=0.3),
        _frame_with_index_tip(ts_ms=100, tip_x=0.55),
        _frame_with_index_tip(ts_ms=200, tip_x=0.32),
        _frame_with_index_tip(ts_ms=300, tip_x=0.58),
        _frame_with_index_tip(ts_ms=400, tip_x=0.34),
    ]
    det = cls.classify(window)
    assert det is not None
    assert det.name == "wave_motion"
    assert det.modality == "hand"
    assert det.duration_ms == 400
    assert det.metadata["crossings"] >= 2


def test_wave_motion_ignored_when_amplitude_too_small() -> None:
    cls = RuleMovementClassifier(min_amplitude=0.2)
    window = [
        _frame_with_index_tip(ts_ms=0, tip_x=0.50),
        _frame_with_index_tip(ts_ms=100, tip_x=0.51),
        _frame_with_index_tip(ts_ms=200, tip_x=0.49),
        _frame_with_index_tip(ts_ms=300, tip_x=0.51),
    ]
    assert cls.classify(window) is None


def test_nodding_detected() -> None:
    cls = RuleMovementClassifier(min_pitch_rad=0.1)
    window = [
        _frame_with_head(ts_ms=i * 100, pitch=math.sin(i * 1.5) * 0.2)
        for i in range(6)
    ]
    det = cls.classify(window)
    assert det is not None
    assert det.name == "nodding"
    assert det.modality == "head"


def test_shaking_head_detected() -> None:
    cls = RuleMovementClassifier(min_yaw_rad=0.1)
    window = [
        _frame_with_head(ts_ms=i * 100, yaw=math.sin(i * 1.5) * 0.25)
        for i in range(6)
    ]
    det = cls.classify(window)
    assert det is not None
    assert det.name == "shaking_head"
    assert det.modality == "head"


def test_raised_hand_detected_when_wrist_stays_above_threshold() -> None:
    cls = RuleMovementClassifier(raised_hand_y_threshold=0.5, min_amplitude=10.0)
    # 5 frames with the wrist clearly raised (y small).
    frames = []
    for i in range(5):
        landmarks = [Landmark(x=0.5, y=0.2)] + [Landmark(x=0.5, y=0.2)] * 20
        hand = HandPose(hand="right", landmarks=landmarks, confidence=0.9)
        frames.append(VisionFrame(ts_ms=i * 100, hands=[hand]))
    det = cls.classify(frames)
    assert det is not None
    assert det.name == "raised_hand"


def test_window_too_short_returns_none() -> None:
    cls = RuleMovementClassifier()
    assert cls.classify([]) is None
    assert cls.classify([_frame_with_index_tip(ts_ms=0, tip_x=0.5)]) is None
