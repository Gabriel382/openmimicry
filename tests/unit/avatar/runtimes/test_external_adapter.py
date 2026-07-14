"""Unit tests for ``ExternalAvatarAdapter``.

Same shape as the Unity adapter tests but for the generic protocol:
frame shapes, reconnect, bounded queue drop-oldest, reverse-channel
counters (``ack`` / ``ready`` / ``error``), and the shutdown frame.
"""

from __future__ import annotations

import asyncio

import pytest
from openmimicry.avatar.runtimes.external.adapter import ExternalAvatarAdapter
from openmimicry.avatar.runtimes.external.client import MockExternalClient
from openmimicry.core.contracts import AvatarRuntimeAdapter
from openmimicry.core.schemas import AvatarDirective


async def _wait_for(predicate, *, timeout: float = 1.0, step: float = 0.01) -> bool:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(step)
    return predicate()


def test_adapter_satisfies_avatar_runtime_protocol() -> None:
    assert isinstance(ExternalAvatarAdapter(client=MockExternalClient()), AvatarRuntimeAdapter)


def test_runtime_name_and_capabilities() -> None:
    adapter = ExternalAvatarAdapter(client=MockExternalClient())
    assert adapter.name == "external"
    assert {"external", "gestures", "gaze", "expressions"} <= adapter.capabilities


async def test_load_character_sends_load_frame() -> None:
    c = MockExternalClient()
    adapter = ExternalAvatarAdapter(client=c)
    try:
        await adapter.load_character("anya", {"asset_url": "https://example.test/anya.glb"})
        assert await _wait_for(lambda: len(c.sent_frames) >= 1)
    finally:
        await adapter.shutdown()
    frame = c.sent_frames[0]
    assert frame["type"] == "load.character"
    assert frame["id"] == "anya"
    assert frame["asset_url"] == "https://example.test/anya.glb"


async def test_apply_directive_sends_external_directive() -> None:
    c = MockExternalClient()
    adapter = ExternalAvatarAdapter(client=c)
    try:
        await adapter.apply_directive(
            AvatarDirective(state="happy", emotion="happy", intensity=0.4)
        )
        assert await _wait_for(lambda: len(c.sent_frames) >= 1)
    finally:
        await adapter.shutdown()
    frame = c.sent_frames[0]
    assert frame["type"] == "avatar.directive"
    assert frame["runtime"] == "external"
    assert frame["directive"]["emotion"] == "happy"
    assert frame["directive"]["intensity"] == pytest.approx(0.4)


async def test_set_text_set_visibility_emit_distinct_frames() -> None:
    c = MockExternalClient()
    adapter = ExternalAvatarAdapter(client=c)
    try:
        await adapter.set_text("hello world")
        await adapter.set_visibility(False)
        assert await _wait_for(lambda: len(c.sent_frames) >= 2)
    finally:
        await adapter.shutdown()
    kinds = [f["type"] for f in c.sent_frames]
    assert "set.text" in kinds
    assert "set.visibility" in kinds


async def test_start_stop_speaking_send_quick_toggles() -> None:
    c = MockExternalClient()
    adapter = ExternalAvatarAdapter(client=c)
    try:
        await adapter.start_speaking("hi there")
        await adapter.stop_speaking()
        assert await _wait_for(lambda: len(c.sent_frames) >= 2)
    finally:
        await adapter.shutdown()
    directive_frames = [f for f in c.sent_frames if f["type"] == "avatar.directive"]
    assert directive_frames[0]["speaking"] is True
    assert directive_frames[0]["text"] == "hi there"
    assert directive_frames[1]["speaking"] is False


async def test_healthcheck_reflects_client_state() -> None:
    c = MockExternalClient()
    adapter = ExternalAvatarAdapter(client=c)
    try:
        assert await adapter.healthcheck() is False
        await adapter.apply_directive(AvatarDirective(state="idle"))
        assert await _wait_for(adapter.healthcheck)
    finally:
        await adapter.shutdown()
    assert await adapter.healthcheck() is False


async def test_shutdown_sends_shutdown_frame_when_client_open() -> None:
    c = MockExternalClient()
    adapter = ExternalAvatarAdapter(client=c)
    await adapter.apply_directive(AvatarDirective(state="idle"))
    await _wait_for(lambda: len(c.sent_frames) >= 1)
    await adapter.shutdown()
    assert any(f.get("type") == "shutdown" for f in c.sent_frames)


async def test_shutdown_is_idempotent() -> None:
    adapter = ExternalAvatarAdapter(client=MockExternalClient())
    await adapter.shutdown()
    await adapter.shutdown()


async def test_send_after_disconnect_resends_against_a_fresh_open_client() -> None:
    c = MockExternalClient()
    adapter = ExternalAvatarAdapter(client=c)
    try:
        await adapter.apply_directive(AvatarDirective(state="idle"))
        assert await _wait_for(lambda: len(c.sent_frames) >= 1)
        c.simulate_disconnect()
        await c.connect()
        await adapter.apply_directive(AvatarDirective(state="speaking", speaking=True))
        assert await _wait_for(lambda: len(c.sent_frames) >= 2, timeout=2.0)
    finally:
        await adapter.shutdown()


async def test_queue_drops_oldest_when_renderer_is_unreachable(caplog) -> None:
    c = MockExternalClient(fail_until_attempt=10_000)
    adapter = ExternalAvatarAdapter(client=c, queue_max=4)
    try:
        for _ in range(20):
            await adapter.apply_directive(AvatarDirective(state="idle"))
            await asyncio.sleep(0)
        assert adapter.queue_size <= 4
    finally:
        await adapter.shutdown()
    assert any("queue full" in record.getMessage().lower() for record in caplog.records)


async def test_ack_ready_error_counters() -> None:
    c = MockExternalClient()
    adapter = ExternalAvatarAdapter(client=c)
    try:
        await adapter.apply_directive(AvatarDirective(state="idle"))
        await _wait_for(lambda: len(c.sent_frames) >= 1)
        await c.feed_incoming({"type": "ready"})
        await c.feed_incoming({"type": "ack", "for": "avatar.directive"})
        await c.feed_incoming({"type": "ack", "for": "avatar.directive"})
        await c.feed_incoming({"type": "error", "message": "boom"})
        assert await _wait_for(lambda: adapter.acks_received >= 2)
        assert adapter.ready_received >= 1
        assert any(e["message"] == "boom" for e in adapter.errors_received)
    finally:
        await adapter.shutdown()


def test_factory_returns_adapter_with_mock_client() -> None:
    from openmimicry.avatar.runtimes.external.adapter import (
        make_external_avatar_adapter,
    )

    adapter = make_external_avatar_adapter()
    assert isinstance(adapter, ExternalAvatarAdapter)
    assert isinstance(adapter.client, MockExternalClient)
