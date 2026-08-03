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
* ``task.cancel`` -> cancel a running task when its adapter supports it.
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
    ErrorEvent,
    EventBus,
    SpeechController,
)

from .conversation import TurnSubmission
from .projection import project_messages
from .supervisor import TurnSource

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
        self._send_locks: dict[WebSocket, asyncio.Lock] = {}
        self._lock = asyncio.Lock()
        self._latest_avatar: dict[str, Any] | None = None
        self._latest_bubble: dict[str, Any] | None = None
        self._latest_runtime: dict[str, Any] | None = None
        self._latest_turn: dict[str, Any] | None = None
        self._component_health: dict[str, dict[str, Any]] = {}
        self._latest_tasks: dict[str, dict[str, Any]] = {}
        self._conversation: dict[str, dict[str, Any]] = {}

    async def add_socket(self, ws: WebSocket) -> bool:
        async with self._lock:
            self._sockets.add(ws)
            self._send_locks.setdefault(ws, asyncio.Lock())
            replay = [message for message in (self._latest_runtime,) if message is not None]
            replay.extend(self._component_health.values())
            replay.extend(
                message
                for message in (self._latest_turn, self._latest_avatar, self._latest_bubble)
                if message is not None
            )
            replay.extend(self._conversation.values())
            replay.extend(self._latest_tasks.values())
        for message in replay:
            if not await self.send(ws, message):
                return False
        return True

    async def remove_socket(self, ws: WebSocket) -> None:
        async with self._lock:
            self._sockets.discard(ws)
            self._send_locks.pop(ws, None)

    @property
    def socket_count(self) -> int:
        return len(self._sockets)

    async def publish(self, message: dict[str, Any]) -> None:
        """Fan ``message`` out to every connected socket. Never raises."""
        dead: list[WebSocket] = []
        async with self._lock:
            self._remember_unlocked(message)
            sockets = list(self._sockets)
        for ws in sockets:
            if not await self.send(ws, message, remove_on_failure=False):
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._sockets.discard(ws)
                    self._send_locks.pop(ws, None)

    async def send(
        self,
        ws: WebSocket,
        message: dict[str, Any],
        *,
        remove_on_failure: bool = True,
    ) -> bool:
        """Serialize all writes to one socket and absorb close/send races."""

        async with self._lock:
            if ws not in self._sockets:
                return False
            send_lock = self._send_locks.setdefault(ws, asyncio.Lock())
        try:
            async with send_lock:
                await ws.send_json(message)
        except Exception as exc:
            _log.info("WebSocket send dropped: type=%s error=%s", message.get("type"), exc)
            if remove_on_failure:
                await self.remove_socket(ws)
            return False
        return True

    async def remember(self, message: dict[str, Any]) -> None:
        """Retain UI state so windows opened later receive a coherent view."""

        async with self._lock:
            self._remember_unlocked(message)

    def _remember_unlocked(self, message: dict[str, Any]) -> None:
        if message.get("type") == "avatar.directive":
            self._latest_avatar = dict(message)
        elif message.get("type") == "runtime.state":
            self._latest_runtime = dict(message)
        elif message.get("type") == "turn.state":
            # A rejected attempt is not the current turn and must not replace
            # the authoritative state replayed to newly opened windows.
            if message.get("state") != "rejected":
                self._latest_turn = dict(message)
        elif message.get("type") == "component.health":
            component = message.get("component")
            if isinstance(component, str) and component:
                self._component_health[component] = dict(message)
        elif message.get("type") == "bubble.text":
            if message.get("reset") is True:
                self._latest_bubble = None
            elif message.get("complete") is True:
                self._latest_bubble = dict(message)
        elif message.get("type") == "conversation.turn":
            turn_id = message.get("id")
            if isinstance(turn_id, str) and turn_id:
                self._conversation[turn_id] = dict(message)
                while len(self._conversation) > 100:
                    self._conversation.pop(next(iter(self._conversation)))
        elif message.get("type") == "task.card":
            update = message.get("update")
            handle = update.get("handle") if isinstance(update, dict) else None
            task_id = handle.get("id") if isinstance(handle, dict) else None
            if isinstance(task_id, str) and task_id:
                self._latest_tasks[task_id] = dict(message)


# ---------------------------------------------------------------------------
# WS endpoint
# ---------------------------------------------------------------------------


HandleUserText = Callable[[str, TurnSource], Awaitable[TurnSubmission]]
GetModeStatus = Callable[[], dict[str, Any]]
CancelTask = Callable[[dict[str, Any]], Awaitable[None]]


async def ws_endpoint(
    websocket: WebSocket,
    *,
    bus: EventBus,
    speech: SpeechController,
    bridge: BroadcastBridge,
    handle_user_text: HandleUserText,
    apply_mode_toggle: Callable[[str, bool], Awaitable[None]] | None = None,
    get_mode_status: GetModeStatus | None = None,
    cancel_task: CancelTask | None = None,
) -> None:
    """The single ``/ws`` route.

    Spawns a downstream pump that projects bus events and a loop that
    reads inbound JSON. Either ending tears both down cleanly.
    """
    await websocket.accept()
    if not await bridge.add_socket(websocket):
        return
    if get_mode_status is not None:
        sent = await bridge.send(
            websocket,
            {
                "type": "system.notice",
                "level": "info",
                "message": "voice_status",
                "voice": get_mode_status(),
            },
        )
        if not sent:
            return
    _log.info("WS connected; total=%d", bridge.socket_count)

    pump_task = asyncio.create_task(
        _projection_pump(websocket, bus, bridge),
        name="openmimicry.backend.ws.pump",
    )

    try:
        while True:
            try:
                payload = await websocket.receive_json()
            except (WebSocketDisconnect, RuntimeError):
                # Starlette can raise RuntimeError instead of
                # WebSocketDisconnect when an application shutdown races a
                # pending receive. It is a normal terminal state, not an ASGI
                # application failure.
                break

            await _dispatch_inbound(
                payload,
                bus=bus,
                speech=speech,
                handle_user_text=handle_user_text,
                apply_mode_toggle=apply_mode_toggle,
                cancel_task=cancel_task,
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


async def _projection_pump(websocket: WebSocket, bus: EventBus, bridge: BroadcastBridge) -> None:
    """Subscribe to ``bus``, project each event, ``send_json`` to ``ws``."""
    sub = bus.subscribe()
    try:
        async for event in sub:
            for message in project_messages(event):
                await bridge.remember(message)
                if not await bridge.send(websocket, message):
                    return
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        _log.warning("WS projection pump crashed: %s", exc, exc_info=True)


async def _dispatch_inbound(
    payload: dict[str, Any],
    *,
    bus: EventBus,
    speech: SpeechController,
    handle_user_text: HandleUserText,
    apply_mode_toggle: Callable[[str, bool], Awaitable[None]] | None,
    cancel_task: CancelTask | None,
) -> None:
    msg_type = payload.get("type") if isinstance(payload, dict) else None
    if msg_type == "user.text":
        text = str(payload.get("text") or "").strip()
        if not text:
            return
        # Admission is fast and non-blocking: accepted work continues on the
        # coordinator's owned task; a concurrent turn is rejected immediately.
        await handle_user_text(text, "text")
        return

    if msg_type == "ptt.down":
        try:
            await speech.ptt_down()
        except Exception as exc:
            _log.warning("ptt.down failed: %s", exc)
            bus.publish(ErrorEvent(ts=_now(), where="voice.ptt", message=str(exc)))
            return
        bus.publish(
            ConfigUpdated(
                ts=_now(),
                diff={"ptt_active": True, "ptt_stage": "listening"},
            )
        )
        return

    if msg_type == "ptt.up":
        bus.publish(
            ConfigUpdated(
                ts=_now(),
                diff={"ptt_active": True, "ptt_stage": "transcribing"},
            )
        )
        try:
            await speech.ptt_up()
        except Exception as exc:
            _log.warning("ptt.up failed: %s", exc)
            bus.publish(ErrorEvent(ts=_now(), where="voice.ptt", message=str(exc)))
            bus.publish(
                ConfigUpdated(
                    ts=_now(),
                    diff={"ptt_active": False, "ptt_stage": "error"},
                )
            )
            return
        bus.publish(ConfigUpdated(ts=_now(), diff={"ptt_active": False}))
        return

    if msg_type == "mode.toggle":
        key = str(payload.get("key") or "")
        value = bool(payload.get("value"))
        if apply_mode_toggle is not None:
            try:
                await apply_mode_toggle(key, value)
            except Exception as exc:
                _log.warning("apply_mode_toggle(%r, %r) raised: %s", key, value, exc)
                bus.publish(
                    ErrorEvent(
                        ts=_now(),
                        where="voice.mode",
                        message=str(exc),
                    )
                )
                return
        bus.publish(ConfigUpdated(ts=_now(), diff={key: value}))
        return

    if msg_type == "task.cancel":
        handle = payload.get("handle")
        if cancel_task is not None and isinstance(handle, dict):
            try:
                await cancel_task(handle)
            except Exception as exc:
                bus.publish(ErrorEvent(ts=_now(), where="backend.task.cancel", message=str(exc)))
        return

    _log.info("WS: ignoring unknown inbound type=%r", msg_type)
