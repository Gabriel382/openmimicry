from __future__ import annotations

import asyncio

from openmimicry_backend.conversation import ConversationCoordinator, ConversationMemory


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


async def test_coordinator_serializes_turns_and_records_only_completed_replies() -> None:
    active = 0
    maximum_active = 0
    histories: list[list[str]] = []

    async def run_turn(text, history):
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        histories.append([message.content for message in history])
        await asyncio.sleep(0.01)
        active -= 1
        return None if text == "failed" else f"reply:{text}"

    coordinator = ConversationCoordinator(run_turn=run_turn, history_turns=4)
    await asyncio.gather(
        coordinator.submit("first"),
        coordinator.submit("failed"),
        coordinator.submit("third"),
    )

    assert maximum_active == 1
    assert histories[0] == []
    assert histories[1] == ["first", "reply:first"]
    assert histories[2] == ["first", "reply:first"]
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

    coordinator = ConversationCoordinator(run_turn=run_turn)
    first = coordinator.submit_background("first")
    second = coordinator.submit_background("second")
    await asyncio.sleep(0)

    assert first.done() is False
    assert second.done() is False
    release.set()
    await asyncio.gather(first, second)
    await coordinator.close()
