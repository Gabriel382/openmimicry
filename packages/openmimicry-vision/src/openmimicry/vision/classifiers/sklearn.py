"""Scikit-learn gesture classifier — loads a joblib bundle.

The expected bundle shape::

    {
        "estimator": fitted sklearn estimator with ``predict`` (and
                     optionally ``predict_proba``),
        "labels":    list[str]   # class index → gesture name
    }

Heavy deps (``joblib``, ``numpy``) are lazy-imported. Without the
``[sklearn]`` extra installed, instantiation raises
:class:`ClassifierUnavailable`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openmimicry.core.schemas import GestureDetection, HandPose

from .base import ClassifierUnavailable

__all__ = [
    "SklearnGestureClassifier",
    "make_sklearn_classifier",
]


_log = logging.getLogger(__name__)


class SklearnGestureClassifier:
    name: str = "sklearn"

    def __init__(
        self,
        *,
        path: str | None = None,
        threshold: float = 0.6,
        labels: list[str] | None = None,
    ) -> None:
        if not path:
            raise ClassifierUnavailable("SklearnGestureClassifier requires path=<.joblib bundle>")
        self._path = Path(path).expanduser()
        self._threshold = max(0.0, min(1.0, threshold))
        self._labels_override = list(labels) if labels else None
        self._estimator: Any = None
        self._labels: list[str] = []
        self._load()

    def _load(self) -> None:
        try:
            import joblib  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ClassifierUnavailable(
                'joblib is not installed. Install with `pip install "openmimicry-vision[sklearn]"`.'
            ) from exc
        try:
            bundle = joblib.load(self._path)
        except FileNotFoundError as exc:
            raise ClassifierUnavailable(f"sklearn bundle not found at {self._path}") from exc
        except Exception as exc:
            raise ClassifierUnavailable(
                f"failed to load sklearn bundle {self._path}: {exc}"
            ) from exc

        if isinstance(bundle, dict) and "estimator" in bundle:
            self._estimator = bundle["estimator"]
            labels = bundle.get("labels") or []
        else:
            # Allow a bare estimator (labels then come from constructor).
            self._estimator = bundle
            labels = []
        self._labels = self._labels_override or list(labels)
        if not hasattr(self._estimator, "predict"):
            raise ClassifierUnavailable(f"sklearn bundle at {self._path} has no .predict()")

    def classify(self, pose: HandPose) -> GestureDetection | None:
        if self._estimator is None or len(pose.landmarks) < 21:
            return None
        try:
            import numpy as np  # type: ignore[import-not-found]
        except ImportError:
            return None
        vec = _featurise(pose, np)
        try:
            if hasattr(self._estimator, "predict_proba"):
                proba = self._estimator.predict_proba(vec.reshape(1, -1))[0]
                idx = int(proba.argmax())
                confidence = float(proba[idx])
            else:
                idx = int(self._estimator.predict(vec.reshape(1, -1))[0])
                confidence = 1.0
        except Exception as exc:
            _log.warning("SklearnGestureClassifier predict raised: %s", exc)
            return None
        if confidence < self._threshold:
            return None
        name = self._labels[idx] if 0 <= idx < len(self._labels) else str(idx)
        return GestureDetection(
            name=name,
            modality="hand",
            hand=pose.hand,
            confidence=confidence,
            source="sklearn",
            pose=pose,
        )


def _featurise(pose: HandPose, np: Any) -> Any:
    arr = np.array([[lm.x, lm.y, lm.z] for lm in pose.landmarks], dtype="float32")
    # Center on the wrist so the classifier is translation-invariant.
    arr = arr - arr[0]
    return arr.flatten()


def make_sklearn_classifier(**kwargs: Any) -> SklearnGestureClassifier:
    return SklearnGestureClassifier(**kwargs)
