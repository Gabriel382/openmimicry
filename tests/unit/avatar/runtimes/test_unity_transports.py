"""Unit tests for ``MockUnityTransport`` and ``WSUnityTransport``.

The mock transport is fully covered. ``WSUnityTransport`` only has its
lazy-import error path exercised in CI; the real WS path is exercised
by manual smoke against a Unity process.
"""

from __future__ import annotations

import asyncio

import pytest
from openmimicry.avatar.runtimes.unity.transports import (
    MockUnityTransport,
    UnityTransport,
    UnityTransportError,
    UnityTransportUnavailable,
    WSUnityTransport,
)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


def test_mock_satisfies_unity_transport_protocol() -> None:
    assert isinstance(MockUnityTransport(), UnityTransport)


def test_ws_transport_satisfies_unity_transport_protocol() -> None:
    assert isinstance(WSUnityTransport("ws://localhost"), UnityTransport)


# ---------------------------------------------------------------------------
# MockUnityTransport behaviour
# ---------------------------------------------------------------------------


async def test_send_records_frame_after_connect() -> None:
    t = MockUnityTransport()
    await t.connect()
    await t.send({"type": "ping"})
    assert t.sent_frames == [{"type": "ping"}]
    assert t.is_open is True


async def test_send_before_connect_raises() -> None:
    t = MockUnityTransport()
    with pytest.raises(UnityTransportError):
        await t.send({"type": "ping"})


async def test_close_closes_and_yields_sentinel() -> None:
    t = MockUnityTransport()
    await t.connect()
    await t.aclose()
    # Pulling incoming() after close exits cleanly.
    items = [item async for item in t.incoming()]
    assert items == []
    assert t.is_open is False


async def test_fail_until_attempt_retries_until_threshold() -> None:
    t = MockUnityTransport(fail_until_attempt=2)
    with pytest.raises(UnityTransportError):
        await t.connect()
    with pytest.raises(UnityTransportError):
        await t.connect()
    await t.connect()  # third attempt succeeds
    assert t.is_open is True


async def test_simulate_disconnect_blocks_next_send() -> None:
    t = MockUnityTransport()
    await t.connect()
    await t.send({"type": "first"})
    t.simulate_disconnect()
    with pytest.raises(UnityTransportError):
        await t.send({"type": "second"})


async def test_feed_incoming_yields_to_iterator() -> None:
    t = MockUnityTransport()
    await t.connect()
    await t.feed_incoming({"type": "ack", "for": "avatar.directive"})

    async def _drain() -> list[dict]:
        items: list[dict] = []
        async for frame in t.incoming():
            items.append(frame)
            if len(items) == 1:
                await t.aclose()
        return items

    received = await asyncio.wait_for(_drain(), timeout=0.5)
    assert received == [{"type": "ack", "for": "avatar.directive"}]


# ---------------------------------------------------------------------------
# WSUnityTransport — lazy-import error path
# ---------------------------------------------------------------------------


async def test_ws_transport_raises_unavailable_when_websockets_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Force the lazy-import to fail regardless of whether `websockets` is
    # installed in the dev env. The transport's `_import_websockets`
    # helper raises `UnityTransportUnavailable` on `ImportError`.
    import openmimicry.avatar.runtimes.unity.transports as mod

    def _boom() -> None:
        raise UnityTransportUnavailable("forced for test")

    monkeypatch.setattr(mod, "_import_websockets", _boom)
    t = WSUnityTransport("ws://does-not-matter")
    with pytest.raises(UnityTransportUnavailable):
        await t.connect()
