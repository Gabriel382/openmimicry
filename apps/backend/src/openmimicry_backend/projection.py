"""``project(event) -> dict | None``: RuntimeEvent -> frontend wire-protocol.

The wire protocol is defined in ``docs/contracts.md`` §9. There are six
inbound message shapes (server -> frontend):

* ``avatar.directive`` — emitted by the avatar runtime via its WSBridge,
  **not** synthesised here. Director state-transitions trigger the runtime,
  the runtime calls ``WSBridge.publish(...)``, and that lands on the
  socket alongside our projected events. This projector therefore
  returns ``None`` for events that the avatar director would map to
  directives (``LLMStarted``, ``TTSStarted``, ``UserSpeechStarted``,
  …) — duplication would let the same state flip twice on the wire.
* ``transcript.preview`` — partial STT projection.
* ``bubble.text`` — LLM token stream and final reply.
* ``conversation.turn`` — replayable user/assistant history for the dashboard.
* ``task.card`` — TaskSubmitted / TaskUpdatedEvent / TaskCompleted.
* ``system.notice`` — wake detection, config updates, errors,
  TTSInterrupted user-facing warnings.

Every projection returns a plain JSON-serialisable ``dict``. Pydantic
models are dumped with ``model_dump(mode="json")`` so ``datetime`` -> ISO
string and ``set`` -> ``list``.
"""

from __future__ import annotations

import logging
from typing import Any

from openmimicry.core.schemas import (
    AvatarCue,
    ComponentHealthChanged,
    ConfigUpdated,
    ErrorEvent,
    LLMReplyComplete,
    LLMStarted,
    LLMTokenStreamed,
    RuntimeEvent,
    RuntimeStateChanged,
    TaskCompleted,
    TaskSubmitted,
    TaskUpdate,
    TaskUpdatedEvent,
    TranscriptPreview,
    TTSChunkSpoken,
    TTSFailed,
    TTSFinished,
    TTSInterrupted,
    TTSQueued,
    TTSReady,
    TTSStarted,
    TurnStateChanged,
    UserSpeechFinal,
    UserSpeechStarted,
    UserTextSubmitted,
    WakeDetected,
)

__all__ = ["project", "project_messages"]


_log = logging.getLogger(__name__)


def project(event: RuntimeEvent) -> dict[str, Any] | None:
    """Map ``event`` to a wire-protocol dict, or ``None`` to suppress.

    Returning ``None`` is significant — it means "this event is already
    represented on the wire by some other producer" (typically the avatar
    runtime emitting ``avatar.directive``).
    """
    if isinstance(event, TranscriptPreview):
        return {
            "type": "transcript.preview",
            "text": event.text,
            "is_final": event.is_final,
        }

    if isinstance(event, TurnStateChanged):
        return {
            "type": "turn.state",
            "turn_id": event.turn_id,
            "sequence": event.sequence,
            "state": event.state,
            "source": event.source,
            "reason": event.reason,
            "active_turn_id": event.active_turn_id,
            "ts": event.ts.isoformat(),
        }

    if isinstance(event, RuntimeStateChanged):
        return {
            "type": "runtime.state",
            "instance_id": event.instance_id,
            "state": event.state,
            "ready": event.ready,
            "reason": event.reason,
            "ts": event.ts.isoformat(),
        }

    if isinstance(event, ComponentHealthChanged):
        return {
            "type": "component.health",
            "instance_id": event.instance_id,
            "component": event.component,
            "family": event.family,
            "adapter": event.adapter,
            "state": event.state,
            "required": event.required,
            "actual_device": event.actual_device,
            "last_error": event.last_error,
            "ts": event.ts.isoformat(),
        }

    if isinstance(event, LLMTokenStreamed):
        return {
            "type": "bubble.text",
            "text": event.delta,
            "complete": False,
        }

    if isinstance(event, LLMReplyComplete):
        if event.presentation_mode == "voice_only":
            return None
        return {
            "type": "bubble.text",
            "text": event.full_text,
            "complete": True,
            "presentation_mode": event.presentation_mode,
            "speech_expected": event.speech_expected,
            "utterance_id": event.speech_utterance_id,
        }

    if isinstance(event, TaskSubmitted):
        # Synthesise a TaskUpdate with status "queued" so the frontend has
        # a uniform shape for the task.card schema.
        synthetic = TaskUpdate(
            handle=event.handle,
            status="queued",
            note=event.summary,
            ts=event.ts,
        )
        return {"type": "task.card", "update": synthetic.model_dump(mode="json")}

    if isinstance(event, TaskUpdatedEvent):
        return {
            "type": "task.card",
            "update": event.update.model_dump(mode="json"),
        }

    if isinstance(event, TaskCompleted):
        # TaskCompleted -> task.card with the result projected as a final
        # TaskUpdate. The status is whatever the result carries.
        final = TaskUpdate(
            handle=event.handle,
            status=event.result.status,
            note=event.result.summary,
            artifacts=event.result.artifacts,
            error=event.result.error,
            ts=event.ts,
        )
        return {"type": "task.card", "update": final.model_dump(mode="json")}

    if isinstance(event, WakeDetected):
        return {
            "type": "system.notice",
            "level": "info",
            "message": f"wake:{event.name}",
        }

    if isinstance(event, TTSInterrupted):
        return {
            "type": "system.notice",
            "level": "warn",
            "message": "tts_interrupted",
        }

    if isinstance(event, ConfigUpdated):
        return {
            "type": "system.notice",
            "level": "info",
            "message": "config_updated",
            "diff": event.diff,
        }

    if isinstance(event, ErrorEvent):
        return {
            "type": "system.notice",
            "level": "error",
            "message": event.message,
            "where": event.where,
            "recoverable": event.recoverable,
        }

    # Events that are intentionally suppressed because the avatar runtime
    # (via its WSBridge) emits the canonical avatar.directive for them, OR
    # because they're internal bookkeeping the frontend doesn't see.
    if isinstance(
        event,
        UserTextSubmitted
        | AvatarCue
        | UserSpeechStarted
        | UserSpeechFinal
        | LLMStarted
        | TTSQueued
        | TTSReady
        | TTSStarted
        | TTSChunkSpoken
        | TTSFinished
        | TTSFailed,
    ):
        return None

    _log.debug(
        "projection.project: no mapping for event kind=%r; suppressing",
        getattr(event, "kind", type(event).__name__),
    )
    return None


def project_messages(event: RuntimeEvent) -> list[dict[str, Any]]:
    """Return every wire message represented by one runtime event.

    ``project`` remains the frozen one-event/one-message compatibility surface.
    This additive wrapper supplies UI-only turn boundaries, conversation
    history, and speech-result diagnostics without changing runtime events.
    """

    event_id = f"{event.kind}:{event.ts.isoformat()}"

    speech_status: str | None = None
    if isinstance(event, TTSQueued):
        speech_status = "queued"
    elif isinstance(event, TTSReady):
        speech_status = "ready"
    elif isinstance(event, TTSStarted):
        speech_status = "started"
    elif isinstance(event, TTSFinished):
        speech_status = "finished"
    elif isinstance(event, TTSInterrupted):
        speech_status = "interrupted"
    elif isinstance(event, TTSFailed):
        speech_status = "failed"
    if speech_status is not None:
        utterance_id = getattr(event, "utterance_id", None)
        messages = [
            {
                "type": "speech.status",
                "utterance_id": utterance_id,
                "status": speech_status,
            }
        ]
        compatibility = project(event)
        if compatibility is not None:
            messages.append(compatibility)
        if isinstance(event, TTSFailed):
            messages.append(
                {
                    "type": "system.notice",
                    "level": "error",
                    "message": event.message,
                    "where": "voice.tts",
                    "recoverable": True,
                }
            )
        return messages

    if isinstance(event, LLMStarted):
        return [
            {
                "type": "bubble.text",
                "text": "",
                "complete": False,
                "reset": True,
            }
        ]

    if isinstance(event, UserTextSubmitted):
        return [
            {
                "type": "conversation.turn",
                "id": event_id,
                "role": "user",
                "source": "text",
                "text": event.text,
                "ts": event.ts.isoformat(),
            }
        ]

    if isinstance(event, UserSpeechFinal):
        displayed = (event.raw_text or event.text).strip()
        messages: list[dict[str, Any]] = [
            {
                "type": "system.notice",
                "level": "info" if event.accepted else "warn",
                "message": "speech_result",
                "voice_result": {
                    "text": displayed,
                    "command": event.text,
                    "reason": event.reason,
                    "accepted": event.accepted,
                    "input_mode": event.input_mode,
                    "rejection_reason": event.rejection_reason,
                },
            }
        ]
        if displayed:
            messages.append(
                {
                    "type": "conversation.turn",
                    "id": event_id,
                    "role": "user",
                    "source": "voice",
                    "text": displayed,
                    "ts": event.ts.isoformat(),
                    "accepted": event.accepted,
                    "rejection_reason": event.rejection_reason,
                    "command": event.text,
                }
            )
        return messages

    base = project(event)
    messages = [base] if base is not None else []
    if isinstance(event, LLMReplyComplete) and event.full_text:
        messages.append(
            {
                "type": "conversation.turn",
                "id": event_id,
                "role": "assistant",
                "source": "assistant",
                "text": event.full_text,
                "ts": event.ts.isoformat(),
            }
        )
    return messages
