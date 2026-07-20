from __future__ import annotations

import asyncio
from typing import Any

from openmimicry.core import EventBus
from openmimicry_backend.ws import BroadcastBridge, ws_endpoint


class _ShutdownSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.messages: list[dict[str, Any]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict[str, Any]) -> None:
        self.messages.append(message)

    async def receive_json(self) -> dict[str, Any]:
        raise RuntimeError("WebSocket is not connected. Need to call accept first.")


async def test_shutdown_runtime_error_is_a_clean_disconnect() -> None:
    socket = _ShutdownSocket()
    bus = EventBus()
    bridge = BroadcastBridge()

    async def handle_user_text(_text: str, _source: str) -> None:
        raise AssertionError("shutdown socket must not dispatch input")

    try:
        await ws_endpoint(
            socket,  # type: ignore[arg-type]
            bus=bus,
            speech=object(),  # type: ignore[arg-type]
            bridge=bridge,
            handle_user_text=handle_user_text,
        )
    finally:
        await bus.aclose()

    assert socket.accepted is True
    assert bridge.socket_count == 0


class _ClosedOnSendSocket(_ShutdownSocket):
    async def send_json(self, _message: dict[str, Any]) -> None:
        raise RuntimeError('Cannot call "send" once a close message has been sent.')


async def test_status_send_racing_with_close_is_a_clean_disconnect() -> None:
    socket = _ClosedOnSendSocket()
    bus = EventBus()
    bridge = BroadcastBridge()

    try:
        await ws_endpoint(
            socket,  # type: ignore[arg-type]
            bus=bus,
            speech=object(),  # type: ignore[arg-type]
            bridge=bridge,
            handle_user_text=lambda _text, _source: asyncio.sleep(0),
            get_mode_status=lambda: {"agent_voice": True},
        )
    finally:
        await bus.aclose()

    assert bridge.socket_count == 0


class _ConcurrencyCheckingSocket(_ShutdownSocket):
    def __init__(self) -> None:
        super().__init__()
        self.sending = False
        self.overlap = False

    async def send_json(self, message: dict[str, Any]) -> None:
        if self.sending:
            self.overlap = True
        self.sending = True
        await asyncio.sleep(0.01)
        self.messages.append(message)
        self.sending = False


async def test_bridge_serializes_concurrent_writes_per_socket() -> None:
    socket = _ConcurrencyCheckingSocket()
    bridge = BroadcastBridge()
    await bridge.add_socket(socket)  # type: ignore[arg-type]

    await asyncio.gather(
        bridge.publish({"type": "one"}),
        bridge.publish({"type": "two"}),
    )

    assert socket.overlap is False
    assert len(socket.messages) == 2
