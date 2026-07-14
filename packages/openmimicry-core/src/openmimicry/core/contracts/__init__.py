"""Frozen Protocols for every cross-module adapter surface.

Source of truth: ``docs/contracts.md`` §2–§6. Every contract in this package
is ``@runtime_checkable`` so adapter implementations can be checked with
``isinstance(obj, LLMAdapter)`` in tests.
"""

from __future__ import annotations

from .avatar import AvatarDirector, AvatarOrchestrator, AvatarRuntimeAdapter
from .bus import EventBus
from .llm import LLMAdapter
from .tasks import TaskRuntimeAdapter
from .vision import (
    BodyDetector,
    GestureClassifier,
    HandDetector,
    HeadDetector,
    LandmarkDetector,
    MovementClassifier,
    VisionAdapter,
)
from .voice import OnChunk, SpeechController, STTAdapter, TTSAdapter, WakeController

__all__ = [
    "AvatarDirector",
    "AvatarOrchestrator",
    "AvatarRuntimeAdapter",
    "BodyDetector",
    "EventBus",
    "GestureClassifier",
    "HandDetector",
    "HeadDetector",
    "LLMAdapter",
    "LandmarkDetector",
    "MovementClassifier",
    "OnChunk",
    "STTAdapter",
    "SpeechController",
    "TTSAdapter",
    "TaskRuntimeAdapter",
    "VisionAdapter",
    "WakeController",
]
