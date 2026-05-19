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
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openmimicry.core import (
    LLMReplyComplete,
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

    try:
        await asyncio.wait_for(_drain(), timeout=timeout)
    except asyncio.TimeoutError:
        pass
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
    assert "llm_token" in kinds
    assert "llm_done" in kinds

    last_token = max(i for i, k in enumerate(kinds) if k == "llm_token")
    first_done = kinds.index("llm_done")
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
