"""MediaPipe Pose detector (33-point body skeleton).

Same lazy-import + Protocol shape as the hands detector. The
landmark count is the MediaPipe Pose contract (33 points indexed
0..32 — left/right wrist/elbow/shoulder/etc.).
"""

from __future__ import annotations

import logging
from typing import Any

from openmimicry.core.schemas import BodyPose, Landmark

from .base import MediaPipeUnavailable, import_mediapipe

__all__ = [
    "MediaPipePoseDetector",
    "make_mediapipe_pose_detector",
]


_log = logging.getLogger(__name__)


class MediaPipePoseDetector:
    """Wraps ``mediapipe.solutions.pose.Pose``."""

    name: str = "mediapipe_pose"
    modality: str = "body"

    def __init__(
        self,
        *,
        min_detection_confidence: float = 0.6,
        min_tracking_confidence: float = 0.6,
        model_complexity: int = 1,
        enable_segmentation: bool = False,
        smooth_landmarks: bool = True,
    ) -> None:
        self._min_detection = min_detection_confidence
        self._min_tracking = min_tracking_confidence
        self._model_complexity = model_complexity
        self._enable_segmentation = enable_segmentation
        self._smooth_landmarks = smooth_landmarks
        self._pose: Any = None
        self._ready: bool = False

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def warmup(self) -> None:
        if self._ready:
            return
        mp = import_mediapipe()
        try:
            self._pose = mp.solutions.pose.Pose(
                min_detection_confidence=self._min_detection,
                min_tracking_confidence=self._min_tracking,
                model_complexity=self._model_complexity,
                enable_segmentation=self._enable_segmentation,
                smooth_landmarks=self._smooth_landmarks,
            )
        except Exception as exc:
            raise MediaPipeUnavailable(
                f"failed to construct mediapipe.solutions.pose.Pose: {exc}"
            ) from exc
        self._ready = True

    async def shutdown(self) -> None:
        pose = self._pose
        self._pose = None
        self._ready = False
        if pose is None:
            return
        try:
            pose.close()
        except Exception as exc:
            _log.debug("MediaPipePoseDetector close raised: %s", exc)

    async def detect(self, frame_bgr: Any) -> BodyPose | None:
        if not self._ready or self._pose is None:
            return None
        try:
            import cv2  # type: ignore[import-not-found]
        except ImportError:
            return None

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self._pose.process(rgb)
        if result.pose_landmarks is None:
            return None
        landmarks = [
            Landmark(
                x=lm.x,
                y=lm.y,
                z=lm.z,
                visibility=lm.visibility,
                presence=getattr(lm, "presence", None),
            )
            for lm in result.pose_landmarks.landmark
        ]
        # MediaPipe Pose doesn't surface a single confidence; mean
        # visibility is a reasonable proxy.
        confidences = [
            lm.visibility for lm in result.pose_landmarks.landmark if lm.visibility is not None
        ]
        confidence = float(sum(confidences) / len(confidences)) if confidences else 1.0
        return BodyPose(landmarks=landmarks, confidence=confidence)


def make_mediapipe_pose_detector(**kwargs: Any) -> MediaPipePoseDetector:
    return MediaPipePoseDetector(**kwargs)
