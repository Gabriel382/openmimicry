from __future__ import annotations

from openmimicry.core import EventBus, RuntimeStateChanged, TurnStateChanged
from openmimicry_backend.supervisor import RuntimeSupervisor, TurnAdmission


async def test_turn_lease_rejects_overlap_and_only_owner_can_release() -> None:
    bus = EventBus()
    events = bus.subscribe()
    supervisor = RuntimeSupervisor(bus=bus, initial_state="ready", instance_id="runtime-1")

    first = await supervisor.try_begin_turn(source="text")
    assert first.accepted is True
    accepted = await anext(events)
    thinking = await anext(events)
    assert isinstance(accepted, TurnStateChanged) and accepted.state == "accepted"
    assert isinstance(thinking, TurnStateChanged) and thinking.state == "thinking"

    overlap = await supervisor.try_begin_turn(source="wake")
    assert overlap.accepted is False
    assert overlap.reason == "turn_in_progress"
    assert overlap.active_turn_id == first.turn_id
    rejected = await anext(events)
    assert isinstance(rejected, TurnStateChanged) and rejected.state == "rejected"

    impostor = TurnAdmission(
        accepted=True,
        turn_id="not-the-owner",
        sequence=99,
        source="text",
    )
    assert await supervisor.complete_turn(impostor) is False
    assert supervisor.active_turn_id == first.turn_id
    assert await supervisor.complete_turn(first) is True
    completed = await anext(events)
    assert isinstance(completed, TurnStateChanged) and completed.state == "completed"
    assert supervisor.can_accept_turn is True
    await events.aclose()
    await bus.aclose()


async def test_runtime_state_blocks_admission_until_ready() -> None:
    bus = EventBus()
    events = bus.subscribe()
    supervisor = RuntimeSupervisor(bus=bus, instance_id="runtime-2")

    rejected = await supervisor.try_begin_turn(source="text")
    assert rejected.reason == "runtime_starting"
    await anext(events)

    await supervisor.set_runtime_state("ready")
    ready = await anext(events)
    assert isinstance(ready, RuntimeStateChanged)
    assert ready.ready is True

    admitted = await supervisor.try_begin_turn(source="text")
    assert admitted.accepted is True
    await events.aclose()
    await bus.aclose()
