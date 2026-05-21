"""Unit tests for AvatarOrchestrator — bus integration + swap_runtime invariant."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from openmimicry.avatar.director import AvatarDirector
from openmimicry.avatar.mocks import MockAvatarRuntimeAdapter
from openmimicry.avatar.orchestrator import AvatarOrchestrator
from openmimicry.core.bus import EventBus
from openmimicry.core.schemas import (
    TaskCompleted,
    TTSFinished,
    TTSStarted,
    UserSpeechStarted,
)
from openmimicry.core.schemas.app import AvatarConfig
from openmimicry.core.schemas.tasks import TaskHandle, TaskResult


def _ts() -> datetime:
    return datetime.now(timezone.utc)


_HANDLE = TaskHandle(id="t", runtime="mock")
_RESULT = TaskResult(handle=_HANDLE, status="succeeded")


async def _wait_for(predicate, *, timeout: float = 1.0, poll: float = 0.01) -> None:
    """Poll ``predicate()`` until it returns truthy or ``timeout`` expires."""
    loop = asyncio.get_event_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        if predicate():
            return
        await asyncio.sleep(poll)
    raise AssertionError(f"predicate never became true within {timeout}s")


async def _make_started_orch():
    bus = EventBus()
    runtime = MockAvatarRuntimeAdapter()
    director = AvatarDirector(config=AvatarConfig(pack="octomimic"))
    orch = AvatarOrchestrator(
        director=director, runtime=runtime, bus=bus, config=director.config
    )
    await orch.start()
    return orch, bus, runtime, director


async def test_start_loads_character_into_runtime() -> None:
    orch, bus, runtime, _director = await _make_started_orch()
    try:
        assert runtime.load_calls == 1
        assert runtime.loaded_character == "octomimic"
    finally:
        await orch.stop()
        await bus.aclose()


async def test_bus_event_produces_directive() -> None:
    orch, bus, runtime, _director = await _make_started_orch()
    try:
        bus.publish(UserSpeechStarted(ts=_ts()))
        await _wait_for(lambda: runtime.directives_received, timeout=0.5)
        assert runtime.directives_received[-1].state == "listening"
    finally:
        await orch.stop()
        await bus.aclose()


async def test_tts_cycle_drives_speaking_then_idle() -> None:
    orch, bus, runtime, _director = await _make_started_orch()
    try:
        bus.publish(TTSStarted(ts=_ts()))
        await _wait_for(
            lambda: any(d.state == "speaking" for d in runtime.directives_received),
            timeout=0.5,
        )
        bus.publish(TTSFinished(ts=_ts()))
        await _wait_for(
            lambda: any(
                d.state == "idle"
                for d in runtime.directives_received
                if d != runtime.directives_received[0]
            ),
            timeout=0.5,
        )
    finally:
        await orch.stop()
        await bus.aclose()


async def test_hold_and_return_for_happy() -> None:
    """``TaskCompleted`` -> happy + scheduled return-to-idle directive."""
    bus = EventBus()
    runtime = MockAvatarRuntimeAdapter()
    director = AvatarDirector(
        config=AvatarConfig(celebration_ms=50)  # short for the test
    )
    orch = AvatarOrchestrator(
        director=director, runtime=runtime, bus=bus, config=director.config
    )
    await orch.start()
    try:
        bus.publish(TaskCompleted(ts=_ts(), handle=_HANDLE, result=_RESULT))
        await _wait_for(
            lambda: any(d.state == "happy" for d in runtime.directives_received),
            timeout=0.5,
        )
        # After celebration_ms, the orchestrator should re-emit an idle directive.
        await _wait_for(
            lambda: any(d.state == "idle" for d in runtime.directives_received[1:]),
            timeout=1.0,
        )
    finally:
        await orch.stop()
        await bus.aclose()


async def test_swap_runtime_preserves_visual_state() -> None:
    """``old.shutdown()`` -> ``new.load_character(...)`` -> ``new.apply_directive(current)``."""
    orch, bus, old_runtime, _director = await _make_started_orch()
    try:
        bus.publish(UserSpeechStarted(ts=_ts()))
        await _wait_for(lambda: old_runtime.directives_received, timeout=0.5)
        current_state = old_runtime.directives_received[-1].state
        assert current_state == "listening"

        new_runtime = MockAvatarRuntimeAdapter()
        await orch.swap_runtime(new_runtime)

        # Old runtime got shut down.
        assert old_runtime.shutdown_calls == 1
        # New runtime got the load_character call.
        assert new_runtime.load_calls == 1
        assert new_runtime.loaded_character == "octomimic"
        # AND the current directive was re-emitted onto it.
        assert any(d.state == "listening" for d in new_runtime.directives_received)
    finally:
        await orch.stop()
        await bus.aclose()


async def test_stop_is_idempotent() -> None:
    orch, bus, runtime, _director = await _make_started_orch()
    await orch.stop()
    await orch.stop()
    assert runtime.shutdown_calls == 1
    await bus.aclose()


async def test_runtime_apply_error_is_logged_not_raised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``runtime.apply_directive`` failing must not crash the consumer."""

    class Boom(MockAvatarRuntimeAdapter):
        async def apply_directive(self, directive) -> None:  # type: ignore[override]
            raise RuntimeError("kaboom")

    bus = EventBus()
    runtime = Boom()
    director = AvatarDirector()
    orch = AvatarOrchestrator(
        director=director, runtime=runtime, bus=bus, config=director.config
    )
    await orch.start()
    try:
        with caplog.at_level("WARNING"):
            bus.publish(UserSpeechStarted(ts=_ts()))
            await asyncio.sleep(0.05)
        assert any("apply_directive" in r.getMessage() for r in caplog.records)
    finally:
        await orch.stop()
        await bus.aclose()
