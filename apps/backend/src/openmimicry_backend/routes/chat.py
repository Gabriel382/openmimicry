"""``POST /chat`` — submit a text turn.

Pipeline:

1. Run :func:`openmimicry.tasks.intent.detect_task_intent` on the input.
2. If a task intent matches, submit to ``wiring.tasks`` (the
   :class:`TaskRouter`) and publish :class:`TaskSubmitted` + a forwarder
   that re-emits every :class:`TaskUpdate` as :class:`TaskUpdatedEvent`
   plus a terminal :class:`TaskCompleted`.
3. Otherwise fall back to the LLM path: ``wiring.llm.generate`` streams
   :class:`LLMChunk`; each chunk publishes :class:`LLMTokenStreamed`;
   final text publishes :class:`LLMReplyComplete`.

The endpoint returns 202 immediately — actual delivery happens on the
WS via :mod:`openmimicry_backend.projection`.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, timezone
from typing import cast
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from openmimicry.core import (
    AvatarCue,
    EventBus,
    LLMAdapter,
    LLMMessage,
    LLMReplyComplete,
    LLMStarted,
    LLMTokenStreamed,
    SpeechController,
    TaskCompleted,
    TaskHandle,
    TaskRequest,
    TaskRuntimeAdapter,
    TaskSubmitted,
    TaskUpdatedEvent,
)
from openmimicry.core.schemas.app import ResponsePresentationConfig
from pydantic import BaseModel

from ..llm_response import load_personality, parse_assistant_reply, speech_safe_text

__all__ = ["ChatRequest", "router", "run_chat_turn"]


_log = logging.getLogger(__name__)
_MIN_THINKING_SECONDS = 0.65
_BACKGROUND_TASK_FORWARDERS: set[asyncio.Task[None]] = set()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ChatRequest(BaseModel):
    text: str


router = APIRouter()


@router.post("/chat", status_code=202, response_model=None)
async def chat(req: ChatRequest, request: Request) -> dict[str, str] | JSONResponse:
    """Atomically submit a turn; never hide an input in a server-side queue."""

    submission = await request.app.state.handle_user_text(req.text, "text")
    if not submission.accepted:
        status_code = 400 if submission.reason == "empty" else 409
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "rejected",
                "reason": submission.reason,
                "turn_id": submission.turn_id,
                "active_turn_id": submission.admission.active_turn_id,
            },
        )
    return {"status": "accepted", "turn_id": submission.turn_id}


async def run_chat_turn(
    text: str,
    *,
    bus: EventBus,
    llm: LLMAdapter,
    tasks: TaskRuntimeAdapter,
    speech: SpeechController | None = None,
    intent_fn: Callable[[str], TaskRequest | None] | None = None,
    history: Sequence[LLMMessage] = (),
    presentation: ResponsePresentationConfig | None = None,
    voice_enabled: bool = True,
    output_language: str = "en",
    tool_fn: Callable[[str], Awaitable[str | None]] | None = None,
) -> str | None:
    """The actual chat/task pipeline. Exposed for direct use in tests.

    ``intent_fn`` defaults to lazy-importing ``openmimicry.tasks.detect_task_intent``
    so tests that drive this function directly don't have to plumb it; the
    HTTP route always passes the classifier off ``wiring.intent`` to keep
    its imports Protocol-only.
    """
    classifier = intent_fn or _lazy_intent_classifier()
    intent = classifier(text)
    if intent is not None:
        bus.publish(LLMStarted(ts=_now()))
        handle = await _run_task_path(intent, bus=bus, tasks=tasks)
        if handle is None:
            return None
        acknowledgements = {
            "fr": "La tâche Claude est lancée en arrière-plan. Je vous préviendrai quand elle sera terminée.",
            "es": "La tarea de Claude se está ejecutando en segundo plano. Te avisaré cuando termine.",
            "pt": "A tarefa do Claude está sendo executada em segundo plano. Avisarei quando terminar.",
            "pt-BR": "A tarefa do Claude está sendo executada em segundo plano. Avisarei quando terminar.",
            "en": "The Claude task is running in the background. I will notify you when it finishes.",
        }
        acknowledgement = acknowledgements.get(output_language, acknowledgements["en"])
        utterance_id = uuid4().hex if speech is not None and voice_enabled else None
        speech_ready = False
        if speech is not None and voice_enabled:
            try:
                if "utterance_id" in inspect.signature(speech.say).parameters:
                    await speech.say(acknowledgement, utterance_id=utterance_id)
                else:
                    legacy_say = cast(Callable[[str], Awaitable[object]], speech.say)
                    await legacy_say(acknowledgement)
                wait_ready = getattr(speech, "wait_until_speech_ready", None)
                if callable(wait_ready):
                    wait_for_audio = cast(Callable[..., Awaitable[object]], wait_ready)
                    timeout = float(getattr(speech, "speech_readiness_timeout_s", 30.0))
                    if "utterance_id" in inspect.signature(wait_ready).parameters:
                        speech_ready = bool(
                            await wait_for_audio(timeout_s=timeout, utterance_id=utterance_id)
                        )
                    else:
                        speech_ready = bool(await wait_for_audio(timeout_s=timeout))
            except Exception:
                _log.warning("could not queue task acknowledgement audio", exc_info=True)
        # Claude acknowledgements are deliberately voice-gated even when the
        # ordinary reply mode is parallel.  The avatar remains in thinking
        # until playback is ready; text and audio then begin together.
        if not speech_ready and speech is not None and voice_enabled:
            _log.warning("task acknowledgement audio unavailable; displaying text fallback")
        bus.publish(LLMTokenStreamed(ts=_now(), delta=acknowledgement))
        bus.publish(
            LLMReplyComplete(
                ts=_now(),
                full_text=acknowledgement,
                presentation_mode="voice_ready" if voice_enabled else "text_only",
                speech_expected=bool(speech_ready),
                speech_utterance_id=utterance_id,
            )
        )
        return acknowledgement
    if tool_fn is not None:
        tool_reply = await tool_fn(text)
        if tool_reply:
            bus.publish(LLMTokenStreamed(ts=_now(), delta=tool_reply))
            bus.publish(LLMReplyComplete(ts=_now(), full_text=tool_reply))
            if speech is not None and voice_enabled:
                try:
                    await speech.say(tool_reply)
                except Exception:
                    _log.warning("could not queue tool confirmation audio", exc_info=True)
            return tool_reply
    return await _run_llm_path(
        text,
        bus=bus,
        llm=llm,
        speech=speech,
        history=history,
        presentation=presentation,
        voice_enabled=voice_enabled,
        output_language=output_language,
    )


def _lazy_intent_classifier() -> Callable[[str], TaskRequest | None]:
    """Import ``detect_task_intent`` only when the route doesn't supply one.

    Pushing the import out of module-load lets `routes.chat` stay clean
    of sibling-package imports at the top of the file.
    """
    from openmimicry.tasks import detect_task_intent

    return detect_task_intent


# ---------------------------------------------------------------------------
# Task path
# ---------------------------------------------------------------------------


async def _run_task_path(
    request_obj: object,
    *,
    bus: EventBus,
    tasks: TaskRuntimeAdapter,
) -> TaskHandle | None:
    # `detect_task_intent` returns a fully-formed TaskRequest.
    try:
        handle = await tasks.submit(request_obj)  # type: ignore[arg-type]
    except Exception as exc:
        from openmimicry.core import ErrorEvent

        bus.publish(ErrorEvent(ts=_now(), where="backend.chat.task", message=str(exc)))
        _log.exception("Task submission failed")
        return None

    _log.info(
        "Task %s submitted: runtime=%s summary=%s",
        handle.id,
        handle.runtime,
        getattr(request_obj, "summary", "") or "",
    )

    bus.publish(
        TaskSubmitted(
            ts=_now(),
            handle=handle,
            summary=getattr(request_obj, "summary", "") or "",
        )
    )

    forwarder = asyncio.create_task(
        _forward_task_path(handle, bus=bus, tasks=tasks),
        name=f"openmimicry.chat.task-forwarder.{handle.id}",
    )
    _BACKGROUND_TASK_FORWARDERS.add(forwarder)
    forwarder.add_done_callback(_BACKGROUND_TASK_FORWARDERS.discard)
    return handle


async def _forward_task_path(
    handle: TaskHandle,
    *,
    bus: EventBus,
    tasks: TaskRuntimeAdapter,
) -> None:
    """Forward progress independently of the conversation turn."""

    # Stream updates back onto the bus.
    try:
        async for update in tasks.updates(handle):
            bus.publish(TaskUpdatedEvent(ts=_now(), update=update))
    except Exception as exc:
        from openmimicry.core import ErrorEvent

        bus.publish(
            ErrorEvent(
                ts=_now(),
                where="backend.chat.task_updates",
                message=str(exc),
            )
        )
        _log.exception("Task %s update stream failed", handle.id)

    try:
        result = await tasks.result(handle)
    except Exception as exc:
        from openmimicry.core import ErrorEvent

        bus.publish(
            ErrorEvent(
                ts=_now(),
                where="backend.chat.task_result",
                message=str(exc),
            )
        )
        _log.exception("Task %s result lookup failed", handle.id)
        return

    bus.publish(TaskCompleted(ts=_now(), handle=handle, result=result))
    if result.status == "succeeded":
        _log.info("Task %s completed successfully", handle.id)
    else:
        detail = result.error.message if result.error is not None else result.summary
        _log.error("Task %s completed with status=%s: %s", handle.id, result.status, detail)
        from openmimicry.core import ErrorEvent

        bus.publish(
            ErrorEvent(
                ts=_now(),
                where="backend.chat.task",
                message=detail or f"Task {handle.id} {result.status}",
            )
        )


# ---------------------------------------------------------------------------
# LLM path
# ---------------------------------------------------------------------------


async def _run_llm_path(
    text: str,
    *,
    bus: EventBus,
    llm: LLMAdapter,
    speech: SpeechController | None,
    history: Sequence[LLMMessage] = (),
    presentation: ResponsePresentationConfig | None = None,
    voice_enabled: bool = True,
    output_language: str = "en",
) -> str | None:
    bus.publish(LLMStarted(ts=_now()))
    thinking_started = asyncio.get_running_loop().time()

    settings = load_personality(output_language=output_language)
    messages = [
        LLMMessage(role="system", content=settings.system_prompt),
        *history,
        LLMMessage(role="user", content=text),
    ]
    raw_parts: list[str] = []
    try:
        async for chunk in llm.generate(messages):
            if chunk.delta:
                raw_parts.append(chunk.delta)
    except Exception as exc:
        from openmimicry.core import ErrorEvent

        bus.publish(ErrorEvent(ts=_now(), where="backend.chat.llm", message=str(exc)))
        # The conversation coordinator owns the turn lease. Propagating the
        # provider failure lets it publish a terminal ``failed`` state and
        # release that lease; swallowing it here left the desktop permanently
        # stuck in ``thinking`` when a provider stream hung or timed out.
        raise

    reply = parse_assistant_reply("".join(raw_parts), settings)
    # Fast local/mock models can otherwise advance from thinking to the reply
    # inside one paint frame. Keep the thinking animation perceptible without
    # adding latency to ordinary network LLM calls that already exceed it.
    thinking_elapsed = asyncio.get_running_loop().time() - thinking_started
    if reply.text and thinking_elapsed < _MIN_THINKING_SECONDS:
        await asyncio.sleep(_MIN_THINKING_SECONDS - thinking_elapsed)
    presentation = presentation or ResponsePresentationConfig()
    mode = presentation.mode
    wants_speech = bool(speech is not None and voice_enabled and reply.text and mode != "text_only")
    utterance_id = uuid4().hex if wants_speech else None

    def publish_reply() -> None:
        # Publish one display update instead of artificial chunks: this clears
        # the previous turn and prevents append-only UI artefacts. Voice-only
        # remains present in conversation history but is suppressed by the
        # bubble projector.
        if reply.text and mode != "voice_only":
            bus.publish(LLMTokenStreamed(ts=_now(), delta=reply.text))
        bus.publish(
            LLMReplyComplete(
                ts=_now(),
                full_text=reply.text,
                presentation_mode=mode,
                speech_expected=wants_speech,
                speech_utterance_id=utterance_id,
            )
        )

    # Parallel/text-only are never gated by audio. This also gives a readable
    # fallback when a driver or optional TTS provider fails.
    if mode in {"parallel", "text_only", "voice_only"}:
        publish_reply()

    speech_ready = False
    if wants_speech and speech is not None:
        try:
            if "utterance_id" in inspect.signature(speech.say).parameters:
                spoken_reply = speech_safe_text(reply.text) or reply.text
                await speech.say(spoken_reply, utterance_id=utterance_id)
            else:
                # Compatibility for third-party v1 SpeechController plugins.
                await speech.say(speech_safe_text(reply.text) or reply.text)
            if mode == "voice_ready":
                wait_ready = getattr(speech, "wait_until_speech_ready", None)
                readiness_timeout_s = float(getattr(speech, "speech_readiness_timeout_s", 30.0))
                if callable(wait_ready):
                    ready_waiter = cast(Callable[..., Awaitable[object]], wait_ready)
                    if "utterance_id" in inspect.signature(wait_ready).parameters:
                        speech_ready = bool(
                            await ready_waiter(
                                timeout_s=readiness_timeout_s,
                                utterance_id=utterance_id,
                            )
                        )
                    else:
                        speech_ready = bool(await ready_waiter(timeout_s=readiness_timeout_s))
        except Exception as exc:
            _log.warning("could not queue reply audio: %s", exc, exc_info=True)
    if mode == "voice_ready":
        if wants_speech and not speech_ready:
            _log.warning("voice-ready presentation fell back to text because TTS was unavailable")
        publish_reply()
    bus.publish(
        AvatarCue(
            ts=_now(),
            emotion=reply.emotion,
            action=reply.action,
            intensity=reply.intensity,
            duration_ms=reply.duration_ms,
        )
    )
    return reply.text or None
