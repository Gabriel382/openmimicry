from __future__ import annotations

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

    async def handle_user_text(_text: str) -> None:
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
