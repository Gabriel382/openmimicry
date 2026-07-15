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
import logging
from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import APIRouter, Request
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
    TaskRequest,
    TaskRuntimeAdapter,
    TaskSubmitted,
    TaskUpdatedEvent,
    UserTextSubmitted,
)
from pydantic import BaseModel

from ..llm_response import load_personality, parse_assistant_reply

__all__ = ["ChatRequest", "router", "run_chat_turn"]


_log = logging.getLogger(__name__)
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()
_MIN_THINKING_SECONDS = 0.65


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ChatRequest(BaseModel):
    text: str


router = APIRouter()


@router.post("/chat", status_code=202)
async def chat(req: ChatRequest, request: Request) -> dict[str, str]:
    wiring = request.app.state.wiring
    bus: EventBus = wiring.bus
    llm: LLMAdapter = wiring.llm
    tasks: TaskRuntimeAdapter = wiring.tasks
    speech: SpeechController = wiring.speech
    intent_fn: Callable[[str], TaskRequest | None] = wiring.intent

    # The WS also publishes UserTextSubmitted on inbound user.text. Here
    # we publish it for callers that hit /chat directly (e.g. curl). The
    # avatar director is idempotent on transitions so a duplicate is a
    # no-op for visible state.
    bus.publish(UserTextSubmitted(ts=_now(), text=req.text))

    # Background pipeline; the HTTP response returns immediately.
    chat_task = asyncio.create_task(
        run_chat_turn(
            req.text,
            bus=bus,
            llm=llm,
            tasks=tasks,
            speech=speech,
            intent_fn=intent_fn,
        ),
        name="openmimicry.backend.chat_turn",
    )
    _BACKGROUND_TASKS.add(chat_task)
    chat_task.add_done_callback(_BACKGROUND_TASKS.discard)
    return {"status": "accepted"}


async def run_chat_turn(
    text: str,
    *,
    bus: EventBus,
    llm: LLMAdapter,
    tasks: TaskRuntimeAdapter,
    speech: SpeechController | None = None,
    intent_fn: Callable[[str], TaskRequest | None] | None = None,
) -> None:
    """The actual chat/task pipeline. Exposed for direct use in tests.

    ``intent_fn`` defaults to lazy-importing ``openmimicry.tasks.detect_task_intent``
    so tests that drive this function directly don't have to plumb it; the
    HTTP route always passes the classifier off ``wiring.intent`` to keep
    its imports Protocol-only.
    """
    classifier = intent_fn or _lazy_intent_classifier()
    intent = classifier(text)
    if intent is not None:
        await _run_task_path(intent, bus=bus, tasks=tasks)
        return
    await _run_llm_path(text, bus=bus, llm=llm, speech=speech)


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
) -> None:
    # `detect_task_intent` returns a fully-formed TaskRequest.
    try:
        handle = await tasks.submit(request_obj)  # type: ignore[arg-type]
    except Exception as exc:
        from openmimicry.core import ErrorEvent

        bus.publish(ErrorEvent(ts=_now(), where="backend.chat.task", message=str(exc)))
        return

    bus.publish(
        TaskSubmitted(
            ts=_now(),
            handle=handle,
            summary=getattr(request_obj, "summary", "") or "",
        )
    )

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
        return

    bus.publish(TaskCompleted(ts=_now(), handle=handle, result=result))


# ---------------------------------------------------------------------------
# LLM path
# ---------------------------------------------------------------------------


async def _run_llm_path(
    text: str,
    *,
    bus: EventBus,
    llm: LLMAdapter,
    speech: SpeechController | None,
) -> None:
    bus.publish(LLMStarted(ts=_now()))
    thinking_started = asyncio.get_running_loop().time()

    settings = load_personality()
    messages = [
        LLMMessage(role="system", content=settings.system_prompt),
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

    reply = parse_assistant_reply("".join(raw_parts), settings)
    # Fast local/mock models can otherwise advance from thinking to the reply
    # inside one paint frame. Keep the thinking animation perceptible without
    # adding latency to ordinary network LLM calls that already exceed it.
    thinking_elapsed = asyncio.get_running_loop().time() - thinking_started
    if reply.text and thinking_elapsed < _MIN_THINKING_SECONDS:
        await asyncio.sleep(_MIN_THINKING_SECONDS - thinking_elapsed)
    for delta in _display_chunks(reply.text):
        bus.publish(LLMTokenStreamed(ts=_now(), delta=delta))
        await asyncio.sleep(0)

    if speech is not None and reply.text:
        await speech.say(reply.text)
        task = getattr(speech, "_current_tts_task", None)
        if task is not None:
            import contextlib

            with contextlib.suppress(Exception):
                await task

    bus.publish(LLMReplyComplete(ts=_now(), full_text=reply.text))
    bus.publish(
        AvatarCue(
            ts=_now(),
            emotion=reply.emotion,
            action=reply.action,
            intensity=reply.intensity,
            duration_ms=reply.duration_ms,
        )
    )


def _display_chunks(text: str, size: int = 48) -> list[str]:
    """Small UI chunks keep the existing bubble protocol deterministic."""

    if not text:
        return []
    return [text[index : index + size] for index in range(0, len(text), size)]
