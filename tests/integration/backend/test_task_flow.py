"""Intent-classified chat -> task pipeline.

``"Ask Claude to summarise readme"`` should NOT hit the LLM. The intent
classifier matches, a :class:`TaskRequest` is submitted to the
:class:`TaskRouter`, and ``task.card`` updates flow on the bus.

We bypass ``TestClient`` here and drive :func:`run_chat_turn` directly
on the test loop so the background task runs on a loop the test owns;
see ``test_chat_flow.py`` for the same rationale.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from openmimicry.core import (
    LLMTokenStreamed,
    RuntimeEvent,
    TaskCompleted,
    TaskSubmitted,
    TaskUpdatedEvent,
)
from openmimicry_backend.routes.chat import run_chat_turn

pytestmark = pytest.mark.integration


async def _collect(bus, n_max: int, *, timeout: float = 2.0) -> list[RuntimeEvent]:
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


async def test_task_intent_routes_to_task_runtime_not_llm(wiring: Any) -> None:
    bus = wiring.bus
    collector = asyncio.create_task(_collect(bus, n_max=30))
    await asyncio.sleep(0)

    await run_chat_turn(
        "Ask Claude to summarise readme",
        bus=bus,
        llm=wiring.llm,
        tasks=wiring.tasks,
        speech=wiring.speech,
    )

    events = await collector
    kinds = [e.kind for e in events]

    assert any(isinstance(e, TaskSubmitted) for e in events)
    assert any(isinstance(e, TaskCompleted) for e in events)
    assert not any(isinstance(e, LLMTokenStreamed) for e in events), (
        f"unexpected llm_token in {kinds!r}"
    )


async def test_task_updates_carry_submitted_handle(wiring: Any) -> None:
    bus = wiring.bus
    collector = asyncio.create_task(_collect(bus, n_max=30))
    await asyncio.sleep(0)

    await run_chat_turn(
        "Use the mcp agent to inspect repo",
        bus=bus,
        llm=wiring.llm,
        tasks=wiring.tasks,
        speech=wiring.speech,
    )

    events = await collector
    submitted = next((e for e in events if isinstance(e, TaskSubmitted)), None)
    assert submitted is not None, "no TaskSubmitted in event stream"
    submitted_id = submitted.handle.id

    updates = [e for e in events if isinstance(e, TaskUpdatedEvent)]
    for u in updates:
        assert u.update.handle.id == submitted_id
