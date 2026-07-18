"""End-to-end ``/chat`` flow exercised against the in-process pipeline.

``TestClient`` runs the FastAPI app in its own event loop; the
``asyncio.create_task`` inside ``POST /chat`` is therefore unobservable
from a test-side ``bus.subscribe()`` on the outer loop. Two assertions
get us full M6 chat-flow coverage anyway:

1. Drive :func:`run_chat_turn` directly on the test loop and assert the
   event sequence on the bus the wiring is using.
2. Hit the actual ``POST /chat`` endpoint through ``TestClient`` to
   prove the HTTP surface returns 202.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openmimicry.core import (
    AvatarCue,
    LLMReplyComplete,
    LLMStarted,
    LLMTokenStreamed,
    RuntimeEvent,
)
from openmimicry_backend.routes.chat import run_chat_turn

pytestmark = pytest.mark.integration


async def _collect_events(bus, n_max: int, *, timeout: float = 2.0) -> list[RuntimeEvent]:
    sub = bus.subscribe()
    collected: list[RuntimeEvent] = []

    async def _drain() -> None:
        async for event in sub:
            collected.append(event)
            if len(collected) >= n_max:
                return

    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(_drain(), timeout=timeout)
    return collected


async def test_chat_pipeline_publishes_llm_stream_then_complete(wiring: Any) -> None:
    """``run_chat_turn`` streams llm_token × N then llm_done on the bus."""
    bus = wiring.bus

    collector = asyncio.create_task(_collect_events(bus, n_max=30))
    await asyncio.sleep(0)

    await run_chat_turn(
        "hi",
        bus=bus,
        llm=wiring.llm,
        tasks=wiring.tasks,
        speech=wiring.speech,
    )

    events = await collector
    kinds = [e.kind for e in events]
    assert any(isinstance(event, LLMStarted) for event in events)
    assert "llm_token" in kinds
    assert "llm_done" in kinds

    first_start = kinds.index("llm_start")
    first_token = kinds.index("llm_token")
    last_token = max(i for i, k in enumerate(kinds) if k == "llm_token")
    first_done = kinds.index("llm_done")
    assert first_start < first_token
    assert last_token < first_done

    deltas = [e.delta for e in events if isinstance(e, LLMTokenStreamed)]
    completes = [e for e in events if isinstance(e, LLMReplyComplete)]
    assert completes, "no LLMReplyComplete published"
    assert completes[-1].full_text == "".join(deltas)


def test_chat_endpoint_returns_202(client: TestClient) -> None:
    """The HTTP surface returns 202 Accepted regardless of pipeline state."""
    resp = client.post("/chat", json={"text": "hi"})
    assert resp.status_code == 202
    assert resp.json() == {"status": "accepted"}


async def test_interrupted_tts_still_completes_the_reply_and_avatar_cue(
    wiring: Any,
) -> None:
    """A normal audio interruption must not abandon the chat state machine."""

    class _InterruptedSpeech:
        _current_tts_task: asyncio.Task[None] | None = None

        async def say(self, _text: str) -> None:
            async def _cancelled() -> None:
                raise asyncio.CancelledError

            self._current_tts_task = asyncio.create_task(_cancelled())

    bus = wiring.bus
    sub = bus.subscribe()

    async def collect_until_cue() -> list[RuntimeEvent]:
        events: list[RuntimeEvent] = []
        async for event in sub:
            events.append(event)
            if isinstance(event, AvatarCue):
                return events
        return events

    collector = asyncio.create_task(collect_until_cue())
    await run_chat_turn(
        "test cancellation",
        bus=bus,
        llm=wiring.llm,
        tasks=wiring.tasks,
        speech=_InterruptedSpeech(),  # type: ignore[arg-type]
        intent_fn=lambda _text: None,
    )
    events = await asyncio.wait_for(collector, timeout=2.0)

    assert any(isinstance(event, LLMReplyComplete) for event in events)
    assert isinstance(events[-1], AvatarCue)


async def test_reply_reaches_ui_before_slow_tts_finishes(wiring: Any) -> None:
    """Voice readiness can never gate delivery of the OpenRouter reply."""

    class _BlockingSpeech:
        def __init__(self) -> None:
            self.entered = asyncio.Event()
            self.release = asyncio.Event()

        async def say(self, _text: str) -> None:
            self.entered.set()
            await self.release.wait()

    speech = _BlockingSpeech()
    sub = wiring.bus.subscribe()

    async def collect_reply() -> LLMReplyComplete:
        async for event in sub:
            if isinstance(event, LLMReplyComplete):
                return event
        raise AssertionError("event subscription closed before the reply")

    collector = asyncio.create_task(collect_reply())
    chat_turn = asyncio.create_task(
        run_chat_turn(
            "voice must not gate text",
            bus=wiring.bus,
            llm=wiring.llm,
            tasks=wiring.tasks,
            speech=speech,  # type: ignore[arg-type]
            intent_fn=lambda _text: None,
        )
    )

    await asyncio.wait_for(speech.entered.wait(), timeout=2.0)
    reply = await asyncio.wait_for(collector, timeout=0.1)
    assert reply.full_text
    assert not chat_turn.done(), "the synthetic TTS job should still be blocked"

    speech.release.set()
    assert await asyncio.wait_for(chat_turn, timeout=1.0) == reply.full_text
