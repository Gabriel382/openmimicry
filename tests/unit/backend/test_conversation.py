from __future__ import annotations

import asyncio

from openmimicry.core import EventBus
from openmimicry_backend.conversation import ConversationCoordinator, ConversationMemory
from openmimicry_backend.supervisor import RuntimeSupervisor


def test_memory_keeps_only_last_four_successful_pairs() -> None:
    memory = ConversationMemory(max_turns=4)
    for index in range(6):
        memory.remember(f"u{index}", f"a{index}")

    assert [message.content for message in memory.messages()] == [
        "u2",
        "a2",
        "u3",
        "a3",
        "u4",
        "a4",
        "u5",
        "a5",
    ]


async def test_coordinator_rejects_overlapping_turns_and_records_only_completed_replies() -> None:
    active = 0
    maximum_active = 0
    histories: list[list[str]] = []
    release = asyncio.Event()

    async def run_turn(text, history):
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        histories.append([message.content for message in history])
        await release.wait()
        active -= 1
        return None if text == "failed" else f"reply:{text}"

    supervisor = RuntimeSupervisor(bus=EventBus(), initial_state="ready")
    coordinator = ConversationCoordinator(
        run_turn=run_turn,
        supervisor=supervisor,
        history_turns=4,
    )
    first = await coordinator.submit_background("first")
    await asyncio.sleep(0)
    rejected = await coordinator.submit_background("overlap")
    assert rejected.accepted is False
    assert rejected.reason == "turn_in_progress"
    assert rejected.admission.active_turn_id == first.turn_id

    release.set()
    assert first.task is not None
    await first.task

    third = await coordinator.submit_background("third")
    assert third.task is not None
    await third.task

    assert maximum_active == 1
    assert histories[0] == []
    assert histories[1] == ["first", "reply:first"]
    assert [message.content for message in coordinator.memory.messages()] == [
        "first",
        "reply:first",
        "third",
        "reply:third",
    ]


async def test_background_submission_returns_before_a_slow_turn_finishes() -> None:
    release = asyncio.Event()

    async def run_turn(text, _history):
        await release.wait()
        return f"reply:{text}"

    supervisor = RuntimeSupervisor(bus=EventBus(), initial_state="ready")
    coordinator = ConversationCoordinator(run_turn=run_turn, supervisor=supervisor)
    first = await coordinator.submit_background("first")
    second = await coordinator.submit_background("second")
    await asyncio.sleep(0)

    assert first.task is not None and first.task.done() is False
    assert second.accepted is False
    assert second.task is None
    release.set()
    await first.task
    await coordinator.close()
