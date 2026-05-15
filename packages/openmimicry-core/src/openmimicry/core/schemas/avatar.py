"""Avatar schemas — frozen Pydantic models.

Source of truth: ``docs/contracts.md`` §2.3 and §2.4. Do not edit signatures here
without going through the contract change procedure (``docs/contracts.md`` §11).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

__all__ = [
    "AvatarDirective",
    "CharacterPack",
    "Emotion",
    "EmotionFrames",
    "State",
]

State = Literal[
    "idle",
    "listening",
    "thinking",
    "speaking",
    "happy",
    "error",
]
"""Runtime avatar state. Extensible in future schema versions."""

Emotion = Literal[
    "neutral",
    "happy",
    "sad",
    "angry",
    "confused",
    "focused",
    "worried",
]
"""Affective dimension applied on top of ``State``."""


class AvatarDirective(BaseModel):
    """A modality-independent directive emitted by ``AvatarDirector``.

    Sprite2D consumes a strict subset (``state``, ``emotion``, ``speaking``);
    Three.js / Live3D / Unity consume the full shape including ``gesture``,
    ``gaze``, ``intensity``, ``duration_ms``, and ``next_state``.
    """

    model_config = ConfigDict(frozen=True)

    state: State
    emotion: Emotion = "neutral"
    animation: str | None = None
    speaking: bool = False
    text: str | None = None
    next_state: State | None = None
    duration_ms: int | None = None
    intensity: float | None = None
    gesture: str | None = None
    gaze: str | None = None
    metadata: dict[str, Any] = {}


class EmotionFrames(BaseModel):
    """The frame configuration for a single emotion in a Sprite2D pack."""

    model_config = ConfigDict(frozen=True)

    frames: str | list[str]
    speaking_frames: str | list[str] | None = None
    fps: int = 10
    loop: bool = True
    return_to: State | None = None
    hold_ms: int | None = None


class CharacterPack(BaseModel):
    """The validated representation of a character pack manifest.

    Concrete pack loading and asset resolution live in ``openmimicry-avatar``.
    Phase 0 only ships the schema.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    id: str
    name: str
    author: str | None = None
    license: str | None = None
    preview: str | None = None
    default_state: State = "idle"
    default_emotion: Emotion = "neutral"
    transition_ms: int = 120
    kind: Literal[
        "sprite2d",
        "advanced2d",
        "threejs",
        "vrm",
        "gltf",
        "unity",
        "external",
    ] = "sprite2d"
    emotions: dict[State, EmotionFrames] = {}
    voice_hint: dict[str, str] = {}
    metadata: dict[str, Any] = {}
