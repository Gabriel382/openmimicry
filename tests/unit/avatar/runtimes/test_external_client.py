"""Unit tests for ``MockExternalClient`` and ``WSExternalClient``."""

from __future__ import annotations

import asyncio

import pytest
from openmimicry.avatar.runtimes.external.client import (
    ExternalClient,
    ExternalClientError,
    ExternalUnavailable,
    MockExternalClient,
    WSExternalClient,
)


def test_mock_satisfies_external_client_protocol() -> None:
    assert isinstance(MockExternalClient(), ExternalClient)


def test_ws_satisfies_external_client_protocol() -> None:
    assert isinstance(WSExternalClient("ws://localhost"), ExternalClient)


async def test_send_records_frame_after_connect() -> None:
    c = MockExternalClient()
    await c.connect()
    await c.send({"type": "ping"})
    assert c.sent_frames == [{"type": "ping"}]
    assert c.is_open is True


async def test_send_before_connect_raises() -> None:
    c = MockExternalClient()
    with pytest.raises(ExternalClientError):
        await c.send({"type": "ping"})


async def test_aclose_yields_sentinel() -> None:
    c = MockExternalClient()
    await c.connect()
    await c.aclose()
    items = [item async for item in c.incoming()]
    assert items == []
    assert c.is_open is False


async def test_fail_until_attempt_retries_until_threshold() -> None:
    c = MockExternalClient(fail_until_attempt=2)
    with pytest.raises(ExternalClientError):
        await c.connect()
    with pytest.raises(ExternalClientError):
        await c.connect()
    await c.connect()
    assert c.is_open is True


async def test_simulate_disconnect_blocks_next_send() -> None:
    c = MockExternalClient()
    await c.connect()
    await c.send({"type": "first"})
    c.simulate_disconnect()
    with pytest.raises(ExternalClientError):
        await c.send({"type": "second"})


async def test_feed_incoming_yields_to_iterator() -> None:
    c = MockExternalClient()
    await c.connect()
    await c.feed_incoming({"type": "ack", "for": "avatar.directive"})

    async def _drain() -> list[dict]:
        items: list[dict] = []
        async for frame in c.incoming():
            items.append(frame)
            if len(items) == 1:
                await c.aclose()
        return items

    received = await asyncio.wait_for(_drain(), timeout=0.5)
    assert received == [{"type": "ack", "for": "avatar.directive"}]


async def test_ws_client_raises_unavailable_when_websockets_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import openmimicry.avatar.runtimes.external.client as mod

    def _boom() -> None:
        raise ExternalUnavailable("forced for test")

    monkeypatch.setattr(mod, "_import_websockets", _boom)
    c = WSExternalClient("ws://does-not-matter")
    with pytest.raises(ExternalUnavailable):
        await c.connect()
