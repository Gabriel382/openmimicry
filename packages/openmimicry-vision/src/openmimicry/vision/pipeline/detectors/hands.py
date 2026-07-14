"""MediaPipe Hands detector.

21 landmarks per detected hand, two hands max. The MediaPipe import
is lazy and the detector advertises itself as unavailable when the
extras aren't installed — pipelines treat that as a soft skip
rather than a crash.
"""

from __future__ import annotations

import logging
from typing import Any

from openmimicry.core.schemas import HandPose, Landmark

from .base import MediaPipeUnavailable, import_mediapipe

__all__ = [
    "MediaPipeHandsDetector",
    "make_mediapipe_hands_detector",
]


_log = logging.getLogger(__name__)


class MediaPipeHandsDetector:
    """Wraps ``mediapipe.solutions.hands.Hands``."""

    name: str = "mediapipe_hands"
    modality: str = "hand"

    def __init__(
        self,
        *,
        max_num_hands: int = 2,
        min_detection_confidence: float = 0.6,
        min_tracking_confidence: float = 0.6,
        model_complexity: int = 1,
    ) -> None:
        self._max_num_hands = max_num_hands
        self._min_detection = min_detection_confidence
        self._min_tracking = min_tracking_confidence
        self._model_complexity = model_complexity
        self._hands: Any = None
        self._ready: bool = False

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def warmup(self) -> None:
        if self._ready:
            return
        mp = import_mediapipe()
        try:
            self._hands = mp.solutions.hands.Hands(
                max_num_hands=self._max_num_hands,
                min_detection_confidence=self._min_detection,
                min_tracking_confidence=self._min_tracking,
                model_complexity=self._model_complexity,
            )
        except Exception as exc:
            raise MediaPipeUnavailable(
                f"failed to construct mediapipe.solutions.hands.Hands: {exc}"
            ) from exc
        self._ready = True

    async def shutdown(self) -> None:
        hands = self._hands
        self._hands = None
        self._ready = False
        if hands is None:
            return
        try:
            hands.close()
        except Exception as exc:
            _log.debug("MediaPipeHandsDetector close raised: %s", exc)

    async def detect(self, frame_bgr: Any) -> list[HandPose]:
        if not self._ready or self._hands is None:
            return []
        try:
            import cv2  # type: ignore[import-not-found]
        except ImportError:
            return []

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self._hands.process(rgb)
        poses: list[HandPose] = []
        if not result.multi_hand_landmarks:
            return poses

        # MediaPipe Hands returns parallel lists; handedness can be
        # missing when running in `static_image_mode=False`.
        handedness = result.multi_handedness or []
        for idx, landmarks in enumerate(result.multi_hand_landmarks):
            label = "right"
            score = 1.0
            if idx < len(handedness):
                classification = handedness[idx].classification[0]
                # MediaPipe labels the *mirrored* hand because the
                # camera-facing view sees the user's left hand on the
                # right of the image. We trust the label as-is; users
                # can flip the camera if it's wrong for their setup.
                label = "left" if classification.label.lower() == "left" else "right"
                score = float(classification.score)
            poses.append(
                HandPose(
                    hand=label,  # type: ignore[arg-type]
                    confidence=score,
                    landmarks=[Landmark(x=p.x, y=p.y, z=p.z) for p in landmarks.landmark],
                )
            )
        return poses


def make_mediapipe_hands_detector(**kwargs: Any) -> MediaPipeHandsDetector:
    return MediaPipeHandsDetector(**kwargs)
