"""Reusable hand-pose fixtures for the vision tests.

The 21-point MediaPipe Hands skeleton runs through every gesture
heuristic. We build them by hand here so the tests don't need
recorded image frames.

Coordinates are in normalised image space ``[0, 1]``. ``y`` runs
top→bottom (MediaPipe convention), so a "raised" tip has a *smaller*
``y`` than the wrist.
"""

from __future__ import annotations

from openmimicry.core.schemas import HandPose, Landmark


def _pt(x: float, y: float, z: float = 0.0) -> Landmark:
    return Landmark(x=x, y=y, z=z)


def _hand(landmarks: list[Landmark], *, hand: str = "right") -> HandPose:
    assert len(landmarks) == 21, "hand fixtures must have 21 landmarks"
    return HandPose(hand=hand, landmarks=landmarks, confidence=0.95)  # type: ignore[arg-type]


WRIST = _pt(0.5, 0.8)


# Each finger has 4 joints (MCP, PIP, DIP, TIP). For "extended" we
# place TIP further from the wrist than PIP; for "curled" we keep TIP
# close to the wrist.


def _extended(start_y: float, *, x: float, offset: float = 0.04) -> list[Landmark]:
    return [
        _pt(x, start_y),
        _pt(x, start_y - offset),
        _pt(x, start_y - 2 * offset),
        _pt(x, start_y - 3 * offset),
    ]


def _curled(start_y: float, *, x: float, offset: float = 0.015) -> list[Landmark]:
    return [
        _pt(x, start_y),
        _pt(x, start_y - offset),
        _pt(x, start_y - offset),
        _pt(x, start_y - offset),
    ]


def _thumb_extended() -> list[Landmark]:
    # Thumb is sideways: TIP further to the right than IP, both far
    # from the wrist + MCP.
    return [
        _pt(0.45, 0.78),  # CMC (idx 1)
        _pt(0.4, 0.74),   # MCP (idx 2)
        _pt(0.34, 0.72),  # IP  (idx 3)
        _pt(0.28, 0.70),  # TIP (idx 4)
    ]


def _thumb_curled() -> list[Landmark]:
    return [
        _pt(0.45, 0.78),
        _pt(0.46, 0.77),
        _pt(0.47, 0.76),
        _pt(0.48, 0.78),
    ]


def open_palm_hand() -> HandPose:
    lms = [WRIST] + _thumb_extended()
    lms += _extended(0.7, x=0.46)  # index
    lms += _extended(0.7, x=0.50)  # middle
    lms += _extended(0.7, x=0.54)  # ring
    lms += _extended(0.7, x=0.58)  # pinky
    return _hand(lms)


def fist_hand() -> HandPose:
    lms = [WRIST] + _thumb_curled()
    lms += _curled(0.78, x=0.46)
    lms += _curled(0.78, x=0.50)
    lms += _curled(0.78, x=0.54)
    lms += _curled(0.78, x=0.58)
    return _hand(lms)


def thumbs_up_hand() -> HandPose:
    # Thumb extended upward; other fingers curled.
    thumb = [
        _pt(0.45, 0.78),
        _pt(0.46, 0.72),
        _pt(0.46, 0.66),
        _pt(0.46, 0.60),  # TIP — clearly above MCP
    ]
    lms = [WRIST] + thumb
    lms += _curled(0.78, x=0.46)
    lms += _curled(0.78, x=0.50)
    lms += _curled(0.78, x=0.54)
    lms += _curled(0.78, x=0.58)
    return _hand(lms)


def point_hand() -> HandPose:
    lms = [WRIST] + _thumb_curled()
    lms += _extended(0.7, x=0.46)  # index extended
    lms += _curled(0.78, x=0.50)
    lms += _curled(0.78, x=0.54)
    lms += _curled(0.78, x=0.58)
    return _hand(lms)


def peace_hand() -> HandPose:
    lms = [WRIST] + _thumb_curled()
    lms += _extended(0.7, x=0.46)
    lms += _extended(0.7, x=0.50)
    lms += _curled(0.78, x=0.54)
    lms += _curled(0.78, x=0.58)
    return _hand(lms)


def wave_pose_hand() -> HandPose:
    """Four fingers extended, thumb curled — the static pose used by
    the temporal ``wave_motion`` detector."""
    lms = [WRIST] + _thumb_curled()
    lms += _extended(0.7, x=0.46)
    lms += _extended(0.7, x=0.50)
    lms += _extended(0.7, x=0.54)
    lms += _extended(0.7, x=0.58)
    return _hand(lms)
