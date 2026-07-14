"""Temporal movement classifiers — recent VisionFrame window → movement.

Default implementations:

* :class:`RuleMovementClassifier` — heuristic rules over the recent
  window. Detects ``wave_motion`` (hand index-tip oscillates left↔right),
  ``nodding`` (head pitch oscillates), and ``shaking_head`` (head yaw
  oscillates).
"""

from __future__ import annotations

from .rules import RuleMovementClassifier, make_rule_movement_classifier

__all__ = [
    "RuleMovementClassifier",
    "make_rule_movement_classifier",
]
