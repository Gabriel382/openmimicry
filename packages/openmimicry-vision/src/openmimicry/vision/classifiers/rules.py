"""Pure-Python rule-based hand-gesture classifier.

Operates on the 21-point MediaPipe Hands skeleton::

    0  WRIST
    1..4   THUMB:  CMC, MCP, IP, TIP
    5..8   INDEX:  MCP, PIP, DIP, TIP
    9..12  MIDDLE: MCP, PIP, DIP, TIP
    13..16 RING:   MCP, PIP, DIP, TIP
    17..20 PINKY:  MCP, PIP, DIP, TIP

Coordinates are normalised to ``[0, 1]``. The default heuristics
recognise six gestures: ``open_palm``, ``fist``, ``thumbs_up``,
``point``, ``peace``, ``wave_pose``.

These rules are intentionally robust to small landmark noise. The
sklearn/onnx classifiers can replace them entirely once a trained
model lands.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from openmimicry.core.schemas import GestureDetection, HandPose, Landmark

__all__ = [
    "RuleGestureClassifier",
    "extended_fingers",
    "is_finger_extended",
    "make_rule_classifier",
]


_log = logging.getLogger(__name__)


# Tip / PIP joint indices per finger.
_THUMB_TIP, _THUMB_IP, _THUMB_MCP = 4, 3, 2
_INDEX_TIP, _INDEX_PIP, _INDEX_MCP = 8, 6, 5
_MIDDLE_TIP, _MIDDLE_PIP, _MIDDLE_MCP = 12, 10, 9
_RING_TIP, _RING_PIP, _RING_MCP = 16, 14, 13
_PINKY_TIP, _PINKY_PIP, _PINKY_MCP = 20, 18, 17
_WRIST = 0


def is_finger_extended(
    landmarks: Sequence[Landmark],
    tip_idx: int,
    pip_idx: int,
    mcp_idx: int,
    *,
    margin: float = 0.0,
) -> bool:
    """A non-thumb finger is "extended" when its tip is further from
    the wrist than its PIP joint along the MCP→TIP axis.

    Practically: the tip's distance to the wrist is larger than the
    PIP's distance to the wrist plus a small margin. Works in
    normalised image space without any 3D projection.
    """
    if max(tip_idx, pip_idx, mcp_idx) >= len(landmarks):
        return False
    tip = landmarks[tip_idx]
    pip = landmarks[pip_idx]
    wrist = landmarks[_WRIST]
    d_tip = _dist2(tip, wrist)
    d_pip = _dist2(pip, wrist)
    return d_tip > d_pip + margin


def extended_fingers(landmarks: Sequence[Landmark]) -> dict[str, bool]:
    """Return the extension status of every finger."""
    return {
        "thumb": _thumb_extended(landmarks),
        "index": is_finger_extended(landmarks, _INDEX_TIP, _INDEX_PIP, _INDEX_MCP),
        "middle": is_finger_extended(landmarks, _MIDDLE_TIP, _MIDDLE_PIP, _MIDDLE_MCP),
        "ring": is_finger_extended(landmarks, _RING_TIP, _RING_PIP, _RING_MCP),
        "pinky": is_finger_extended(landmarks, _PINKY_TIP, _PINKY_PIP, _PINKY_MCP),
    }


class RuleGestureClassifier:
    """Pure-function classifier with a heuristic rule per gesture."""

    name: str = "rules"

    def __init__(self, *, threshold: float = 0.6) -> None:
        # Threshold is currently informational; rules either match or
        # don't. We surface it on the detection so downstream policy
        # can decide on confidence cutoffs in a future revision.
        self._threshold = max(0.0, min(1.0, threshold))

    def classify(self, pose: HandPose) -> GestureDetection | None:
        if len(pose.landmarks) < 21:
            return None
        fingers = extended_fingers(pose.landmarks)

        # peace = index + middle up, ring + pinky down
        if fingers["index"] and fingers["middle"] and not fingers["ring"] and not fingers["pinky"]:
            return self._hit("peace", pose, confidence=0.85)

        # point = only index up
        if (
            fingers["index"]
            and not fingers["middle"]
            and not fingers["ring"]
            and not fingers["pinky"]
        ):
            return self._hit("point", pose, confidence=0.85)

        # open_palm = every finger extended (incl. thumb)
        if all(fingers.values()):
            return self._hit("open_palm", pose, confidence=0.9)

        # wave_pose = four fingers up (thumb optional). Used as the
        # static pose for the temporal `wave_motion` movement.
        if fingers["index"] and fingers["middle"] and fingers["ring"] and fingers["pinky"]:
            return self._hit("wave_pose", pose, confidence=0.8)

        # thumbs_up = thumb up, others curled
        if (
            fingers["thumb"]
            and not fingers["index"]
            and not fingers["middle"]
            and not fingers["ring"]
            and not fingers["pinky"]
        ):
            return self._hit("thumbs_up", pose, confidence=0.85)

        # fist = nothing extended
        if not any(fingers.values()):
            return self._hit("fist", pose, confidence=0.8)

        return None

    # ----- internals --------------------------------------------------------

    def _hit(self, name: str, pose: HandPose, *, confidence: float) -> GestureDetection:
        return GestureDetection(
            name=name,
            modality="hand",
            hand=pose.hand,
            confidence=max(confidence, self._threshold),
            source="rules",
            pose=pose,
        )


# Thumb extension is a different rule than the other four: the tip
# travels mostly *sideways* in normalised image space, so distance
# from the wrist alone is unreliable. We compare to the MCP joint
# along the dominant axis.
def _thumb_extended(landmarks: Sequence[Landmark]) -> bool:
    if len(landmarks) <= _THUMB_TIP:
        return False
    tip = landmarks[_THUMB_TIP]
    ip = landmarks[_THUMB_IP]
    mcp = landmarks[_THUMB_MCP]
    wrist = landmarks[_WRIST]
    # Distance tip→wrist must exceed IP→wrist, AND the tip must be
    # further from the MCP than the IP is.
    d_tip_w = _dist2(tip, wrist)
    d_ip_w = _dist2(ip, wrist)
    d_tip_mcp = _dist2(tip, mcp)
    d_ip_mcp = _dist2(ip, mcp)
    return d_tip_w > d_ip_w and d_tip_mcp > d_ip_mcp


def _dist2(a: Landmark, b: Landmark) -> float:
    dx = a.x - b.x
    dy = a.y - b.y
    dz = a.z - b.z
    return dx * dx + dy * dy + dz * dz


def make_rule_classifier(**kwargs: Any) -> RuleGestureClassifier:
    return RuleGestureClassifier(**kwargs)
