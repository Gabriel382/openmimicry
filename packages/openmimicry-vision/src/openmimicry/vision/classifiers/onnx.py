"""ONNX gesture classifier.

The model is expected to take a 1×63 float input (21 landmarks ×
``(x, y, z)``, wrist-centred) and return a (1×N) softmax over class
labels supplied via the ``labels`` config.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openmimicry.core.schemas import GestureDetection, HandPose

from .base import ClassifierUnavailable

__all__ = [
    "OnnxGestureClassifier",
    "make_onnx_classifier",
]


_log = logging.getLogger(__name__)


class OnnxGestureClassifier:
    name: str = "onnx"

    def __init__(
        self,
        *,
        path: str | None = None,
        labels: list[str] | None = None,
        threshold: float = 0.6,
        input_name: str | None = None,
    ) -> None:
        if not path:
            raise ClassifierUnavailable("OnnxGestureClassifier requires path=<.onnx model>")
        if not labels:
            raise ClassifierUnavailable(
                "OnnxGestureClassifier requires labels=[list of class names]"
            )
        self._path = Path(path).expanduser()
        self._labels = list(labels)
        self._threshold = max(0.0, min(1.0, threshold))
        self._input_name_hint = input_name
        self._session: Any = None
        self._input_name: str | None = None
        self._load()

    def _load(self) -> None:
        try:
            import onnxruntime as ort  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ClassifierUnavailable(
                "onnxruntime is not installed. Install with "
                '`pip install "openmimicry-vision[onnx]"`.'
            ) from exc
        try:
            self._session = ort.InferenceSession(str(self._path))
        except FileNotFoundError as exc:
            raise ClassifierUnavailable(f"onnx model not found at {self._path}") from exc
        except Exception as exc:
            raise ClassifierUnavailable(f"failed to load onnx model {self._path}: {exc}") from exc
        # Pick input name.
        try:
            inputs = self._session.get_inputs()
            if self._input_name_hint:
                self._input_name = self._input_name_hint
            elif inputs:
                self._input_name = inputs[0].name
            else:
                self._input_name = "input"
        except Exception:
            self._input_name = self._input_name_hint or "input"

    def classify(self, pose: HandPose) -> GestureDetection | None:
        if self._session is None or len(pose.landmarks) < 21:
            return None
        try:
            import numpy as np  # type: ignore[import-not-found]
        except ImportError:
            return None
        vec = _featurise(pose, np)
        try:
            out = self._session.run(None, {self._input_name: vec.reshape(1, -1)})
        except Exception as exc:
            _log.warning("OnnxGestureClassifier inference raised: %s", exc)
            return None
        if not out:
            return None
        probs = out[0][0]
        try:
            idx = int(probs.argmax())
            confidence = float(probs[idx])
        except Exception:
            return None
        if confidence < self._threshold:
            return None
        name = self._labels[idx] if 0 <= idx < len(self._labels) else str(idx)
        return GestureDetection(
            name=name,
            modality="hand",
            hand=pose.hand,
            confidence=confidence,
            source="onnx",
            pose=pose,
        )


def _featurise(pose: HandPose, np: Any) -> Any:
    arr = np.array([[lm.x, lm.y, lm.z] for lm in pose.landmarks], dtype="float32")
    arr = arr - arr[0]
    return arr.flatten()


def make_onnx_classifier(**kwargs: Any) -> OnnxGestureClassifier:
    return OnnxGestureClassifier(**kwargs)
