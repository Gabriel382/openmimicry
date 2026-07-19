"""Runtime event schemas — the in-process bus payloads.

Source of truth: ``docs/contracts.md`` §2.1 (+ §12 vision amendment).

``RuntimeEvent`` is a discriminated union keyed by the ``kind`` literal so
subscribers can ``match event.kind: case "tts_done": ...`` and Pydantic can
round-trip it through JSON without ambiguity.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from .tasks import TaskHandle, TaskResult, TaskUpdate
from .vision import GestureDetection, MovementDetection

__all__ = [
    "AvatarCue",
    "ConfigUpdated",
    "ConsentRequired",
    "ConsentResolved",
    "ErrorEvent",
    "GestureDetected",
    "HandPoseEnded",
    "HandPoseStarted",
    "LLMReplyComplete",
    "LLMStarted",
    "LLMTokenStreamed",
    "MovementDetected",
    "RuntimeEvent",
    "RuntimeEventAdapter",
    "TTSChunkSpoken",
    "TTSFailed",
    "TTSFinished",
    "TTSInterrupted",
    "TTSQueued",
    "TTSReady",
    "TTSStarted",
    "TaskCompleted",
    "TaskSubmitted",
    "TaskUpdatedEvent",
    "TranscriptPreview",
    "UserSpeechFinal",
    "UserSpeechStarted",
    "UserTextSubmitted",
    "WakeDetected",
]


class _Event(BaseModel):
    """Shared event base. All concrete events freeze their fields."""

    model_config = ConfigDict(frozen=True)

    ts: datetime


class UserTextSubmitted(_Event):
    kind: Literal["user_text"] = "user_text"
    text: str


class UserSpeechStarted(_Event):
    kind: Literal["speech_start"] = "speech_start"


class UserSpeechFinal(_Event):
    kind: Literal["speech_final"] = "speech_final"
    text: str
    reason: Literal["normal", "no_speech", "interrupted"] = "normal"
    # Wake mode now records every final transcript for diagnostics/history,
    # but only accepted turns are submitted to the LLM. ``text`` is the
    # command after wake-prefix stripping; ``raw_text`` is what STT heard.
    accepted: bool = True
    input_mode: Literal["push_to_talk", "continuous", "wake"] = "push_to_talk"
    raw_text: str | None = None
    rejection_reason: Literal["wake_name_missing", "duplicate", "empty"] | None = None


class TranscriptPreview(_Event):
    kind: Literal["transcript_preview"] = "transcript_preview"
    text: str
    is_final: bool = False


class WakeDetected(_Event):
    kind: Literal["wake"] = "wake"
    name: str


class LLMStarted(_Event):
    kind: Literal["llm_start"] = "llm_start"


class LLMTokenStreamed(_Event):
    kind: Literal["llm_token"] = "llm_token"
    delta: str


class LLMReplyComplete(_Event):
    kind: Literal["llm_done"] = "llm_done"
    full_text: str
    presentation_mode: Literal["parallel", "voice_ready", "text_only", "voice_only"] = "parallel"
    speech_expected: bool = False
    speech_utterance_id: str | None = None


class AvatarCue(_Event):
    """Validated affect/action selected from a structured LLM reply.

    ``emotion`` and ``action`` remain strings at the event boundary so packs
    and future runtimes may extend their vocabularies. The backend parser
    allow-lists values before publishing this event.
    """

    kind: Literal["avatar_cue"] = "avatar_cue"
    emotion: str = "neutral"
    action: str = "idle"
    intensity: float = 0.6
    duration_ms: int = 1800


class TTSQueued(_Event):
    kind: Literal["tts_queued"] = "tts_queued"
    utterance_id: str


class TTSReady(_Event):
    kind: Literal["tts_ready"] = "tts_ready"
    utterance_id: str


class TTSStarted(_Event):
    kind: Literal["tts_start"] = "tts_start"
    utterance_id: str | None = None


class TTSChunkSpoken(_Event):
    kind: Literal["tts_chunk"] = "tts_chunk"
    utterance_id: str | None = None


class TTSFinished(_Event):
    kind: Literal["tts_done"] = "tts_done"
    utterance_id: str | None = None


class TTSInterrupted(_Event):
    kind: Literal["tts_interrupted"] = "tts_interrupted"
    utterance_id: str | None = None


class TTSFailed(_Event):
    kind: Literal["tts_failed"] = "tts_failed"
    utterance_id: str | None = None
    message: str = "Text-to-speech playback did not start."


class TaskSubmitted(_Event):
    kind: Literal["task_submitted"] = "task_submitted"
    handle: TaskHandle
    summary: str


class TaskUpdatedEvent(_Event):
    kind: Literal["task_update"] = "task_update"
    update: TaskUpdate


class TaskCompleted(_Event):
    kind: Literal["task_done"] = "task_done"
    handle: TaskHandle
    result: TaskResult


class ConfigUpdated(_Event):
    kind: Literal["config_update"] = "config_update"
    diff: dict


class ErrorEvent(_Event):
    kind: Literal["error"] = "error"
    where: str
    message: str
    recoverable: bool = True


# ---------------------------------------------------------------------------
# Vision events (M13). Additive — no schema_version bump.
# ---------------------------------------------------------------------------


class HandPoseStarted(_Event):
    kind: Literal["hand_pose_start"] = "hand_pose_start"
    hand: Literal["left", "right"]


class HandPoseEnded(_Event):
    kind: Literal["hand_pose_end"] = "hand_pose_end"
    hand: Literal["left", "right"]


class GestureDetected(_Event):
    kind: Literal["gesture"] = "gesture"
    detection: GestureDetection


class MovementDetected(_Event):
    kind: Literal["movement"] = "movement"
    detection: MovementDetection


class ConsentRequired(_Event):
    """Published when a privacy-sensitive subsystem (vision) is about
    to start. Refuses to open the camera until ``ConsentResolved`` is
    seen."""

    kind: Literal["consent_required"] = "consent_required"
    subsystem: str = "vision"
    reason: str = "camera-capture"


class ConsentResolved(_Event):
    kind: Literal["consent_resolved"] = "consent_resolved"
    subsystem: str = "vision"
    granted: bool = False


RuntimeEvent = Annotated[
    UserTextSubmitted
    | UserSpeechStarted
    | UserSpeechFinal
    | TranscriptPreview
    | WakeDetected
    | LLMStarted
    | LLMTokenStreamed
    | LLMReplyComplete
    | AvatarCue
    | TTSQueued
    | TTSReady
    | TTSStarted
    | TTSChunkSpoken
    | TTSFinished
    | TTSInterrupted
    | TTSFailed
    | TaskSubmitted
    | TaskUpdatedEvent
    | TaskCompleted
    | ConfigUpdated
    | ErrorEvent
    | HandPoseStarted
    | HandPoseEnded
    | GestureDetected
    | MovementDetected
    | ConsentRequired
    | ConsentResolved,
    Field(discriminator="kind"),
]
"""Discriminated union over every runtime event variant.

The discriminator is the ``kind`` literal so parsing untrusted JSON resolves
to the correct subclass deterministically.
"""

RuntimeEventAdapter: TypeAdapter[RuntimeEvent] = TypeAdapter(RuntimeEvent)
"""Pre-built Pydantic ``TypeAdapter`` for fast ``RuntimeEvent`` JSON parsing.

Use ``RuntimeEventAdapter.validate_python(obj)`` or
``RuntimeEventAdapter.validate_json(raw)`` to reconstruct an event with full
discriminator resolution.
"""
