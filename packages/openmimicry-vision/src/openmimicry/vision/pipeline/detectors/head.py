"""Coarse head-pose detector — face-detection bounding box only.

Deliberately small: the project's privacy posture is that always-on
**face-mesh** capture is a poor default. We use MediaPipe's
``FaceDetection`` (returns a bounding box + 6 keypoints) to estimate
a centre + a coarse yaw/pitch from the eye-to-eye + nose-tip
relationship. Mesh-style detectors can land later by registering
themselves under ``openmimicry.contracts.vision_detector[head]``.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from openmimicry.core.schemas import HeadPose, Landmark

from .base import MediaPipeUnavailable, import_mediapipe

__all__ = [
    "MediaPipeHeadDetector",
    "make_mediapipe_head_detector",
]


_log = logging.getLogger(__name__)


class MediaPipeHeadDetector:
    """Wraps ``mediapipe.solutions.face_detection.FaceDetection`` —
    returns a small 6-DoF :class:`HeadPose`."""

    name: str = "mediapipe_head"
    modality: str = "head"

    def __init__(
        self,
        *,
        min_detection_confidence: float = 0.6,
        model_selection: int = 0,
    ) -> None:
        self._min_detection = min_detection_confidence
        self._model_selection = model_selection
        self._detector: Any = None
        self._ready: bool = False

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def warmup(self) -> None:
        if self._ready:
            return
        mp = import_mediapipe()
        try:
            self._detector = mp.solutions.face_detection.FaceDetection(
                min_detection_confidence=self._min_detection,
                model_selection=self._model_selection,
            )
        except Exception as exc:  # noqa: BLE001
            raise MediaPipeUnavailable(
                f"failed to construct mediapipe.solutions.face_detection.FaceDetection: {exc}"
            ) from exc
        self._ready = True

    async def shutdown(self) -> None:
        detector = self._detector
        self._detector = None
        self._ready = False
        if detector is None:
            return
        try:
            detector.close()
        except Exception as exc:  # noqa: BLE001
            _log.debug("MediaPipeHeadDetector close raised: %s", exc)

    async def detect(self, frame_bgr: Any) -> HeadPose | None:
        if not self._ready or self._detector is None:
            return None
        try:
            import cv2  # type: ignore[import-not-found]
        except ImportError:
            return None

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self._detector.process(rgb)
        if not result.detections:
            return None

        # Pick the largest bbox.
        det = max(
            result.detections,
            key=lambda d: (
                d.location_data.relative_bounding_box.width
                * d.location_data.relative_bounding_box.height
            ),
        )
        bbox = det.location_data.relative_bounding_box
        kp = det.location_data.relative_keypoints  # 6 keypoints
        # MediaPipe face_detection keypoint order:
        # 0=right_eye, 1=left_eye, 2=nose_tip, 3=mouth_center,
        # 4=right_ear_tragion, 5=left_ear_tragion.
        center_x = bbox.xmin + bbox.width / 2.0
        center_y = bbox.ymin + bbox.height / 2.0
        yaw = pitch = roll = 0.0
        if len(kp) >= 3:
            r_eye, l_eye, nose = kp[0], kp[1], kp[2]
            # Roll: angle between eyes.
            roll = math.atan2(l_eye.y - r_eye.y, l_eye.x - r_eye.x)
            # Yaw: nose offset from midpoint of eyes (normalised).
            eye_mid_x = (r_eye.x + l_eye.x) / 2.0
            eye_dx = max(1e-6, l_eye.x - r_eye.x)
            yaw = (nose.x - eye_mid_x) / eye_dx
            yaw = max(-1.0, min(1.0, yaw)) * (math.pi / 4)
            # Pitch: nose vertical offset relative to eye midpoint.
            eye_mid_y = (r_eye.y + l_eye.y) / 2.0
            pitch = (nose.y - eye_mid_y) / max(1e-6, bbox.height) * (math.pi / 3)
        landmarks: list[Landmark] = [Landmark(x=p.x, y=p.y, z=0.0) for p in kp]
        score = float(det.score[0]) if det.score else 1.0
        return HeadPose(
            pitch=pitch,
            yaw=yaw,
            roll=roll,
            center_x=center_x,
            center_y=center_y,
            landmarks=landmarks,
            confidence=score,
        )


def make_mediapipe_head_detector(**kwargs: Any) -> MediaPipeHeadDetector:
    return MediaPipeHeadDetector(**kwargs)
