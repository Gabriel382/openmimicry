"""Runtime event schemas — the in-process bus payloads.

Source of truth: ``docs/contracts.md`` §2.1.

``RuntimeEvent`` is a discriminated union keyed by the ``kind`` literal so
subscribers can ``match event.kind: case "tts_done": ...`` and Pydantic can
round-trip it through JSON without ambiguity.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from .tasks import TaskHandle, TaskResult, TaskUpdate

__all__ = [
    "ConfigUpdated",
    "ErrorEvent",
    "LLMReplyComplete",
    "LLMStarted",
    "LLMTokenStreamed",
    "RuntimeEvent",
    "RuntimeEventAdapter",
    "TTSChunkSpoken",
    "TTSFinished",
    "TTSInterrupted",
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


class TTSStarted(_Event):
    kind: Literal["tts_start"] = "tts_start"


class TTSChunkSpoken(_Event):
    kind: Literal["tts_chunk"] = "tts_chunk"


class TTSFinished(_Event):
    kind: Literal["tts_done"] = "tts_done"


class TTSInterrupted(_Event):
    kind: Literal["tts_interrupted"] = "tts_interrupted"


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


RuntimeEvent = Annotated[
    UserTextSubmitted
    | UserSpeechStarted
    | UserSpeechFinal
    | TranscriptPreview
    | WakeDetected
    | LLMStarted
    | LLMTokenStreamed
    | LLMReplyComplete
    | TTSStarted
    | TTSChunkSpoken
    | TTSFinished
    | TTSInterrupted
    | TaskSubmitted
    | TaskUpdatedEvent
    | TaskCompleted
    | ConfigUpdated
    | ErrorEvent,
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
