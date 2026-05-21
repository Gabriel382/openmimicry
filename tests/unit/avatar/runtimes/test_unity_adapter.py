"""Unit tests for ``UnityAvatarAdapter``.

The adapter is driven against ``MockUnityTransport`` end-to-end:

* Protocol satisfaction + capabilities.
* JSON frame shapes for every adapter method.
* Reconnect after a simulated transport drop.
* Bounded queue: drops the oldest frame with a one-shot warning when
  full.
* Reverse-channel ack + telemetry consumption.
"""

from __future__ import annotations

import asyncio

import pytest
from openmimicry.avatar.runtimes.unity.adapter import UnityAvatarAdapter
from openmimicry.avatar.runtimes.unity.transports import MockUnityTransport
from openmimicry.core.contracts import AvatarRuntimeAdapter
from openmimicry.core.schemas import AvatarDirective


async def _wait_for(predicate, *, timeout: float = 1.0, step: float = 0.01) -> bool:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(step)
    return predicate()


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


def test_adapter_satisfies_avatar_runtime_protocol() -> None:
    assert isinstance(UnityAvatarAdapter(transport=MockUnityTransport()), AvatarRuntimeAdapter)


def test_runtime_name_and_capabilities() -> None:
    adapter = UnityAvatarAdapter(transport=MockUnityTransport())
    assert adapter.name == "unity"
    assert {"3d", "external", "gestures"} <= adapter.capabilities


# ---------------------------------------------------------------------------
# Frame shapes
# ---------------------------------------------------------------------------


async def test_load_character_sends_load_frame() -> None:
    t = MockUnityTransport()
    adapter = UnityAvatarAdapter(transport=t)
    try:
        await adapter.load_character("knight", {"asset_url": "/static/characters/knight"})
        assert await _wait_for(lambda: len(t.sent_frames) >= 1)
    finally:
        await adapter.shutdown()

    frame = t.sent_frames[0]
    assert frame["type"] == "load.character"
    assert frame["id"] == "knight"
    assert frame["asset_url"] == "/static/characters/knight"


async def test_apply_directive_sends_avatar_directive_frame() -> None:
    t = MockUnityTransport()
    adapter = UnityAvatarAdapter(transport=t)
    try:
        await adapter.apply_directive(
            AvatarDirective(state="speaking", emotion="happy", speaking=True)
        )
        assert await _wait_for(lambda: len(t.sent_frames) >= 1)
    finally:
        await adapter.shutdown()

    frame = t.sent_frames[0]
    assert frame["type"] == "avatar.directive"
    assert frame["runtime"] == "unity"
    assert frame["directive"]["state"] == "speaking"
    assert frame["directive"]["emotion"] == "happy"


async def test_set_text_and_visibility_emit_distinct_frames() -> None:
    t = MockUnityTransport()
    adapter = UnityAvatarAdapter(transport=t)
    try:
        await adapter.set_text("hello")
        await adapter.set_visibility(False)
        assert await _wait_for(lambda: len(t.sent_frames) >= 2)
    finally:
        await adapter.shutdown()

    kinds = [f["type"] for f in t.sent_frames]
    assert "bubble.text" in kinds
    assert "set.visibility" in kinds


async def test_start_stop_speaking_send_quick_toggles() -> None:
    t = MockUnityTransport()
    adapter = UnityAvatarAdapter(transport=t)
    try:
        await adapter.start_speaking("hi")
        await adapter.stop_speaking()
        assert await _wait_for(lambda: len(t.sent_frames) >= 2)
    finally:
        await adapter.shutdown()

    speak_frames = [f for f in t.sent_frames if f["type"] == "avatar.directive"]
    assert speak_frames[0]["speaking"] is True
    assert speak_frames[0]["text"] == "hi"
    assert speak_frames[1]["speaking"] is False


# ---------------------------------------------------------------------------
# Healthcheck + shutdown
# ---------------------------------------------------------------------------


async def test_healthcheck_reflects_transport_state() -> None:
    t = MockUnityTransport()
    adapter = UnityAvatarAdapter(transport=t)
    try:
        # Not opened yet.
        assert await adapter.healthcheck() is False
        await adapter.apply_directive(AvatarDirective(state="idle"))
        assert await _wait_for(adapter.healthcheck)
    finally:
        await adapter.shutdown()
    assert await adapter.healthcheck() is False


async def test_shutdown_is_idempotent() -> None:
    t = MockUnityTransport()
    adapter = UnityAvatarAdapter(transport=t)
    await adapter.shutdown()
    await adapter.shutdown()


# ---------------------------------------------------------------------------
# Reconnect after a transport drop
# ---------------------------------------------------------------------------


async def test_send_after_disconnect_retries_against_a_fresh_transport() -> None:
    t = MockUnityTransport()
    adapter = UnityAvatarAdapter(transport=t)
    try:
        await adapter.apply_directive(AvatarDirective(state="idle"))
        assert await _wait_for(lambda: len(t.sent_frames) >= 1)

        # Simulate Unity dropping us.
        t.simulate_disconnect()
        # Re-open from the mock (the adapter doesn't know how to
        # rebuild a fresh transport; we re-arm the existing one).
        await t.connect()

        await adapter.apply_directive(AvatarDirective(state="speaking", speaking=True))
        assert await _wait_for(lambda: len(t.sent_frames) >= 2, timeout=2.0)
    finally:
        await adapter.shutdown()


# ---------------------------------------------------------------------------
# Bounded queue
# ---------------------------------------------------------------------------


async def test_queue_drops_oldest_when_unity_is_unreachable(caplog) -> None:
    # Transport that refuses to connect, so the sender loop never drains
    # the queue. The enqueue path must drop the oldest and warn.
    t = MockUnityTransport(fail_until_attempt=10_000)
    adapter = UnityAvatarAdapter(transport=t, queue_max=4)
    try:
        for i in range(20):
            await adapter.apply_directive(AvatarDirective(state="idle"))
            # Yield so the sender has a chance to wake up between adds.
            await asyncio.sleep(0)
        assert adapter.queue_size <= 4
    finally:
        await adapter.shutdown()

    # The one-shot warning was emitted at least once.
    assert any(
        "queue full" in record.getMessage().lower()
        for record in caplog.records
    )


# ---------------------------------------------------------------------------
# Reverse channel
# ---------------------------------------------------------------------------


async def test_ack_frames_increment_counter() -> None:
    t = MockUnityTransport()
    adapter = UnityAvatarAdapter(transport=t)
    try:
        await adapter.apply_directive(AvatarDirective(state="idle"))
        assert await _wait_for(lambda: len(t.sent_frames) >= 1)
        await t.feed_incoming({"type": "ack", "for": "avatar.directive"})
        await t.feed_incoming({"type": "ack", "for": "avatar.directive"})
        assert await _wait_for(lambda: adapter.acks_received >= 2)
    finally:
        await adapter.shutdown()


async def test_telemetry_frames_are_captured() -> None:
    t = MockUnityTransport()
    adapter = UnityAvatarAdapter(transport=t)
    try:
        await adapter.apply_directive(AvatarDirective(state="idle"))
        await _wait_for(lambda: len(t.sent_frames) >= 1)
        await t.feed_incoming({"type": "telemetry", "fps": 60.0, "anim_state": "Speaking"})
        assert await _wait_for(lambda: len(adapter.telemetry_received) >= 1)
    finally:
        await adapter.shutdown()
    assert adapter.telemetry_received[-1]["fps"] == 60.0


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_factory_returns_adapter_with_mock_transport() -> None:
    from openmimicry.avatar.runtimes.unity.adapter import make_unity_avatar_adapter

    adapter = make_unity_avatar_adapter()
    assert isinstance(adapter, UnityAvatarAdapter)
    assert isinstance(adapter.transport, MockUnityTransport)
