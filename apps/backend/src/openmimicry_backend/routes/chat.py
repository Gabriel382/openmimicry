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
from datetime import datetime, timezone

from collections.abc import AsyncIterator, Callable

from fastapi import APIRouter, Request
from openmimicry.core import (
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

__all__ = ["ChatRequest", "router", "run_chat_turn"]


_log = logging.getLogger(__name__)


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
    asyncio.create_task(
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
    from openmimicry.tasks import detect_task_intent  # noqa: PLC0415

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
    except Exception as exc:  # noqa: BLE001
        from openmimicry.core import ErrorEvent

        bus.publish(
            ErrorEvent(
                ts=_now(), where="backend.chat.task", message=str(exc)
            )
        )
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
    except Exception as exc:  # noqa: BLE001
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
    except Exception as exc:  # noqa: BLE001
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

    # Per the M6 brief's chat-flow ordering (avatar.directive thinking ->
    # bubble.text partials -> avatar.directive speaking -> bubble.text
    # complete -> avatar.directive idle), we feed the speech controller
    # an async generator that yields deltas as they stream. TTSStarted
    # (published by SpeechController) drives the "speaking" transition.
    captured: dict[str, str] = {"full_text": ""}

    async def _delta_stream() -> AsyncIterator[str]:
        try:
            stream = llm.generate([LLMMessage(role="user", content=text)])
            async for chunk in stream:
                if not chunk.delta:
                    continue
                captured["full_text"] += chunk.delta
                bus.publish(LLMTokenStreamed(ts=_now(), delta=chunk.delta))
                yield chunk.delta
        except Exception as exc:  # noqa: BLE001
            from openmimicry.core import ErrorEvent

            bus.publish(
                ErrorEvent(ts=_now(), where="backend.chat.llm", message=str(exc))
            )

    if speech is not None:
        # The speech controller cancels any previous utterance and runs
        # the new one as a background task. We wait for it to finish so
        # `LLMReplyComplete` is published only after the avatar has had
        # a chance to leave the "speaking" state.
        await speech.say(_delta_stream())
        # Wait for the in-flight TTS task to complete (best-effort).
        task = getattr(speech, "_current_tts_task", None)
        if task is not None:
            import contextlib

            with contextlib.suppress(Exception):
                await task
    else:
        # No speech controller: just drain the generator to publish deltas.
        async for _ in _delta_stream():
            pass

    bus.publish(LLMReplyComplete(ts=_now(), full_text=captured["full_text"]))
