"""Rule-based gesture classifier — recognises each shipped gesture."""

from __future__ import annotations

import pytest
from openmimicry.vision.classifiers.rules import (
    RuleGestureClassifier,
    extended_fingers,
)

from ._fixtures import (
    fist_hand,
    open_palm_hand,
    peace_hand,
    point_hand,
    thumbs_up_hand,
    wave_pose_hand,
)


@pytest.fixture
def cls() -> RuleGestureClassifier:
    return RuleGestureClassifier()


def test_open_palm_detected(cls: RuleGestureClassifier) -> None:
    det = cls.classify(open_palm_hand())
    assert det is not None
    assert det.name == "open_palm"
    assert det.confidence >= 0.8
    assert det.modality == "hand"
    assert det.source == "rules"


def test_fist_detected(cls: RuleGestureClassifier) -> None:
    det = cls.classify(fist_hand())
    assert det is not None
    assert det.name == "fist"
    assert det.confidence >= 0.6


def test_thumbs_up_detected(cls: RuleGestureClassifier) -> None:
    det = cls.classify(thumbs_up_hand())
    assert det is not None
    assert det.name == "thumbs_up"


def test_point_detected(cls: RuleGestureClassifier) -> None:
    det = cls.classify(point_hand())
    assert det is not None
    assert det.name == "point"


def test_peace_detected(cls: RuleGestureClassifier) -> None:
    det = cls.classify(peace_hand())
    assert det is not None
    assert det.name == "peace"


def test_wave_pose_detected(cls: RuleGestureClassifier) -> None:
    det = cls.classify(wave_pose_hand())
    assert det is not None
    assert det.name == "wave_pose"


def test_extended_fingers_helper_matches_open_palm() -> None:
    fingers = extended_fingers(open_palm_hand().landmarks)
    assert all(fingers.values())


def test_extended_fingers_helper_matches_fist() -> None:
    fingers = extended_fingers(fist_hand().landmarks)
    assert not any(fingers.values())


def test_short_landmark_list_returns_none(cls: RuleGestureClassifier) -> None:
    from openmimicry.core.schemas import HandPose, Landmark

    pose = HandPose(hand="right", landmarks=[Landmark(x=0, y=0)], confidence=1.0)
    assert cls.classify(pose) is None


def test_detection_carries_pose_reference(cls: RuleGestureClassifier) -> None:
    det = cls.classify(open_palm_hand())
    assert det is not None
    assert det.pose is not None
    assert len(det.pose.landmarks) == 21
