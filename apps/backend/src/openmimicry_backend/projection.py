"""``project(event) -> dict | None``: RuntimeEvent -> frontend wire-protocol.

The wire protocol is defined in ``docs/contracts.md`` §9. There are five
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
    ConfigUpdated,
    ErrorEvent,
    LLMReplyComplete,
    LLMStarted,
    LLMTokenStreamed,
    RuntimeEvent,
    TaskCompleted,
    TaskSubmitted,
    TaskUpdate,
    TaskUpdatedEvent,
    TranscriptPreview,
    TTSChunkSpoken,
    TTSFinished,
    TTSInterrupted,
    TTSStarted,
    UserSpeechFinal,
    UserSpeechStarted,
    UserTextSubmitted,
    WakeDetected,
)

__all__ = ["project"]


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

    if isinstance(event, LLMTokenStreamed):
        return {
            "type": "bubble.text",
            "text": event.delta,
            "complete": False,
        }

    if isinstance(event, LLMReplyComplete):
        return {
            "type": "bubble.text",
            "text": event.full_text,
            "complete": True,
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
        | UserSpeechStarted
        | UserSpeechFinal
        | LLMStarted
        | TTSStarted
        | TTSChunkSpoken
        | TTSFinished,
    ):
        return None

    _log.debug(
        "projection.project: no mapping for event kind=%r; suppressing",
        getattr(event, "kind", type(event).__name__),
    )
    return None
