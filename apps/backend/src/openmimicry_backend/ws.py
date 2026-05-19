"""``ws.py`` — WebSocket endpoint + a multicast :class:`BroadcastBridge`.

The bridge is what the avatar runtime publishes ``avatar.directive``
messages through; every active socket sees them. The same bridge serves
projected :class:`RuntimeEvent`s from the bus — every WS connection opens
its own subscription, projects, and forwards.

The frontend wire protocol is defined in ``docs/contracts.md`` §9. We
accept these inbound messages:

* ``user.text``  -> publish :class:`UserTextSubmitted`
* ``ptt.down`` / ``ptt.up`` -> ``SpeechController.ptt_down/up``
* ``mode.toggle`` -> publish :class:`ConfigUpdated` + apply on the
  speech controller for the two keys it understands.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from openmimicry.core import (
    ConfigUpdated,
    EventBus,
    SpeechController,
    UserTextSubmitted,
)

from .projection import project

__all__ = [
    "BroadcastBridge",
    "ws_endpoint",
]


_log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# BroadcastBridge
# ---------------------------------------------------------------------------


class BroadcastBridge:
    """Process-wide WebSocket fan-out.

    Implements the structural ``WSBridge`` Protocol (``async def
    publish(message: dict) -> None``) without importing it from the
    avatar package — keeps this file free of sibling-package imports.

    Each connected socket is registered via :meth:`add_socket` /
    :meth:`remove_socket` and receives every ``publish`` call. A failed
    send is logged and removes the offending socket from the fan-out
    set so a dead client doesn't poison the broadcast.
    """

    def __init__(self) -> None:
        self._sockets: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def add_socket(self, ws: WebSocket) -> None:
        async with self._lock:
            self._sockets.add(ws)

    async def remove_socket(self, ws: WebSocket) -> None:
        async with self._lock:
            self._sockets.discard(ws)

    @property
    def socket_count(self) -> int:
        return len(self._sockets)

    async def publish(self, message: dict[str, Any]) -> None:
        """Fan ``message`` out to every connected socket. Never raises."""
        if not self._sockets:
            return
        dead: list[WebSocket] = []
        async with self._lock:
            sockets = list(self._sockets)
        for ws in sockets:
            try:
                await ws.send_json(message)
            except Exception as exc:  # noqa: BLE001
                _log.info("BroadcastBridge: socket dropped (%s)", exc)
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._sockets.discard(ws)


# ---------------------------------------------------------------------------
# WS endpoint
# ---------------------------------------------------------------------------


HandleUserText = Callable[[str], Awaitable[None]]


async def ws_endpoint(
    websocket: WebSocket,
    *,
    bus: EventBus,
    speech: SpeechController,
    bridge: BroadcastBridge,
    handle_user_text: HandleUserText,
    apply_mode_toggle: Callable[[str, bool], Awaitable[None]] | None = None,
) -> None:
    """The single ``/ws`` route.

    Spawns a downstream pump that projects bus events and a loop that
    reads inbound JSON. Either ending tears both down cleanly.
    """
    await websocket.accept()
    await bridge.add_socket(websocket)
    _log.info("WS connected; total=%d", bridge.socket_count)

    pump_task = asyncio.create_task(
        _projection_pump(websocket, bus),
        name="openmimicry.backend.ws.pump",
    )

    try:
        while True:
            try:
                payload = await websocket.receive_json()
            except WebSocketDisconnect:
                break

            await _dispatch_inbound(
                payload,
                bus=bus,
                speech=speech,
                handle_user_text=handle_user_text,
                apply_mode_toggle=apply_mode_toggle,
            )
    finally:
        pump_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await pump_task
        await bridge.remove_socket(websocket)
        _log.info("WS disconnected; total=%d", bridge.socket_count)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


async def _projection_pump(websocket: WebSocket, bus: EventBus) -> None:
    """Subscribe to ``bus``, project each event, ``send_json`` to ``ws``."""
    sub = bus.subscribe()
    try:
        async for event in sub:
            message = project(event)
            if message is None:
                continue
            try:
                await websocket.send_json(message)
            except Exception as exc:  # noqa: BLE001
                _log.info("WS pump: send failed (%s); exiting pump", exc)
                return
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        _log.warning("WS projection pump crashed: %s", exc, exc_info=True)


async def _dispatch_inbound(
    payload: dict[str, Any],
    *,
    bus: EventBus,
    speech: SpeechController,
    handle_user_text: HandleUserText,
    apply_mode_toggle: Callable[[str, bool], Awaitable[None]] | None,
) -> None:
    msg_type = payload.get("type") if isinstance(payload, dict) else None
    if msg_type == "user.text":
        text = str(payload.get("text") or "").strip()
        if not text:
            return
        bus.publish(UserTextSubmitted(ts=_now(), text=text))
        await handle_user_text(text)
        return

    if msg_type == "ptt.down":
        await speech.ptt_down()
        return

    if msg_type == "ptt.up":
        await speech.ptt_up()
        return

    if msg_type == "mode.toggle":
        key = str(payload.get("key") or "")
        value = bool(payload.get("value"))
        bus.publish(ConfigUpdated(ts=_now(), diff={key: value}))
        if apply_mode_toggle is not None:
            try:
                await apply_mode_toggle(key, value)
            except Exception as exc:  # noqa: BLE001
                _log.warning("apply_mode_toggle(%r, %r) raised: %s", key, value, exc)
        return

    _log.info("WS: ignoring unknown inbound type=%r", msg_type)
