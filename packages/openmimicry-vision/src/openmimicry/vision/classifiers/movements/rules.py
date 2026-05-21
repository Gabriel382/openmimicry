"""Rule-based temporal-movement classifier.

The classifier consumes a short sequence of :class:`VisionFrame`s
and returns the most-confident movement match. Pure logic — no
numpy, no opencv. Detection criteria:

* ``wave_motion`` — at least 2 zero-crossings of the index-tip
  horizontal-velocity sign across the window AND the tip travelled
  ≥ ``min_amplitude`` (normalised image units).
* ``nodding`` — head pitch crosses zero ≥ 2 times, amplitude ≥
  ``min_pitch_rad``.
* ``shaking_head`` — head yaw crosses zero ≥ 2 times, amplitude ≥
  ``min_yaw_rad``.
* ``raised_hand`` — wrist landmark stays above a configurable y
  threshold across the whole window (``y`` runs top→bottom in
  MediaPipe normalised coords, so "raised" means ``y < threshold``).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from openmimicry.core.schemas import MovementDetection, VisionFrame

__all__ = [
    "RuleMovementClassifier",
    "make_rule_movement_classifier",
]


_log = logging.getLogger(__name__)


_INDEX_TIP = 8
_WRIST = 0


class RuleMovementClassifier:
    """Heuristic movement classifier over a sliding window."""

    name: str = "rules"

    def __init__(
        self,
        *,
        min_amplitude: float = 0.08,
        min_pitch_rad: float = 0.15,
        min_yaw_rad: float = 0.18,
        raised_hand_y_threshold: float = 0.4,
        threshold: float = 0.6,
    ) -> None:
        self._min_amplitude = min_amplitude
        self._min_pitch = min_pitch_rad
        self._min_yaw = min_yaw_rad
        self._raised_y = raised_hand_y_threshold
        self._threshold = max(0.0, min(1.0, threshold))

    def classify(self, window: Sequence[VisionFrame]) -> MovementDetection | None:
        if len(window) < 3:
            return None

        # 1. wave_motion — needs hand landmarks in most of the window.
        wave = self._detect_wave(window)
        if wave is not None:
            return wave

        # 2. raised_hand — sustained pose.
        raised = self._detect_raised_hand(window)
        if raised is not None:
            return raised

        # 3. nodding / shaking — head modalities.
        nod = self._detect_nod(window)
        if nod is not None:
            return nod
        shake = self._detect_shake(window)
        if shake is not None:
            return shake

        return None

    # ------------------------------------------------------------ wave

    def _detect_wave(self, window: Sequence[VisionFrame]) -> MovementDetection | None:
        # Track the index-tip x trajectory. Need ≥3 frames with hands.
        xs: list[tuple[int, float, str]] = []
        for frame in window:
            for hand in frame.hands:
                if len(hand.landmarks) <= _INDEX_TIP:
                    continue
                tip = hand.landmarks[_INDEX_TIP]
                xs.append((frame.ts_ms, tip.x, hand.hand))
        if len(xs) < 3:
            return None
        amplitude = max(x for _, x, _ in xs) - min(x for _, x, _ in xs)
        if amplitude < self._min_amplitude:
            return None
        crossings = _zero_crossings([x for _, x, _ in xs])
        if crossings < 2:
            return None
        duration_ms = max(0, xs[-1][0] - xs[0][0])
        hand_label = _majority_hand([h for _, _, h in xs])
        return MovementDetection(
            name="wave_motion",
            modality="hand",
            hand=hand_label,  # type: ignore[arg-type]
            confidence=min(1.0, max(self._threshold, amplitude * 5)),
            source="rules",
            duration_ms=duration_ms,
            metadata={"amplitude": amplitude, "crossings": crossings},
        )

    # ----------------------------------------------------- raised_hand

    def _detect_raised_hand(self, window: Sequence[VisionFrame]) -> MovementDetection | None:
        seen = 0
        raised = 0
        last_hand: str | None = None
        for frame in window:
            if not frame.hands:
                continue
            for hand in frame.hands:
                if not hand.landmarks:
                    continue
                seen += 1
                last_hand = hand.hand
                if hand.landmarks[_WRIST].y < self._raised_y:
                    raised += 1
        if seen == 0 or raised < seen * 0.8:
            return None
        return MovementDetection(
            name="raised_hand",
            modality="hand",
            hand=last_hand,  # type: ignore[arg-type]
            confidence=self._threshold,
            source="rules",
            duration_ms=max(0, window[-1].ts_ms - window[0].ts_ms),
            metadata={"raised_frames": raised, "seen_frames": seen},
        )

    # ----------------------------------------------------- head nod

    def _detect_nod(self, window: Sequence[VisionFrame]) -> MovementDetection | None:
        pitches = [f.head.pitch for f in window if f.head is not None]
        if len(pitches) < 3:
            return None
        amplitude = max(pitches) - min(pitches)
        if amplitude < self._min_pitch:
            return None
        crossings = _zero_crossings_around(pitches, mean=sum(pitches) / len(pitches))
        if crossings < 2:
            return None
        return MovementDetection(
            name="nodding",
            modality="head",
            confidence=min(1.0, max(self._threshold, amplitude)),
            source="rules",
            duration_ms=max(0, window[-1].ts_ms - window[0].ts_ms),
            metadata={"amplitude": amplitude, "crossings": crossings},
        )

    # ----------------------------------------------------- head shake

    def _detect_shake(self, window: Sequence[VisionFrame]) -> MovementDetection | None:
        yaws = [f.head.yaw for f in window if f.head is not None]
        if len(yaws) < 3:
            return None
        amplitude = max(yaws) - min(yaws)
        if amplitude < self._min_yaw:
            return None
        crossings = _zero_crossings_around(yaws, mean=sum(yaws) / len(yaws))
        if crossings < 2:
            return None
        return MovementDetection(
            name="shaking_head",
            modality="head",
            confidence=min(1.0, max(self._threshold, amplitude)),
            source="rules",
            duration_ms=max(0, window[-1].ts_ms - window[0].ts_ms),
            metadata={"amplitude": amplitude, "crossings": crossings},
        )


def _zero_crossings(series: Sequence[float]) -> int:
    if len(series) < 2:
        return 0
    mean = sum(series) / len(series)
    return _zero_crossings_around(series, mean=mean)


def _zero_crossings_around(series: Sequence[float], *, mean: float) -> int:
    count = 0
    prev_sign = 0
    for value in series:
        centred = value - mean
        sign = 1 if centred > 0 else (-1 if centred < 0 else 0)
        if sign == 0:
            continue
        if prev_sign != 0 and sign != prev_sign:
            count += 1
        prev_sign = sign
    return count


def _majority_hand(labels: Sequence[str]) -> str | None:
    if not labels:
        return None
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    return max(counts.items(), key=lambda kv: kv[1])[0]


def make_rule_movement_classifier(**kwargs: Any) -> RuleMovementClassifier:
    return RuleMovementClassifier(**kwargs)
