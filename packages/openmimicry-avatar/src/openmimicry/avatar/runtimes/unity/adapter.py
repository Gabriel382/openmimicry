"""``UnityAvatarAdapter`` — forwards directives to a Unity process.

The adapter owns three things:

* A pluggable transport (typically :class:`WSUnityTransport`).
* A reconnect loop with exponential backoff (250 ms → 5 s).
* A bounded outbound queue (drop-oldest with a one-shot warning when
  full).

Every :class:`AvatarRuntimeAdapter` method serialises to a JSON frame
and pushes onto the queue. A background sender drains the queue and
delegates to the transport. Reverse-channel frames (``ack`` /
``telemetry``) come back through ``transport.incoming()`` and are
counted on :attr:`acks_received` / :attr:`telemetry_received` for the
panel UI's status chip (a follow-up surfaces these over the bus).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from typing import Any

from openmimicry.core.schemas import AvatarDirective

from .transports import (
    MockUnityTransport,
    UnityFrame,
    UnityTransport,
    UnityTransportError,
    UnityTransportUnavailable,
    WSUnityTransport,
)

__all__ = [
    "UnityAvatarAdapter",
    "UnityTransportUnavailable",
    "make_unity_avatar_adapter",
]


_log = logging.getLogger(__name__)


_INITIAL_BACKOFF_S: float = 0.25
_MAX_BACKOFF_S: float = 5.0
_DEFAULT_QUEUE_MAX: int = 64


class UnityAvatarAdapter:
    """Concrete :class:`AvatarRuntimeAdapter` that talks to Unity."""

    name: str = "unity"

    def __init__(
        self,
        *,
        transport: UnityTransport | None = None,
        url: str | None = None,
        queue_max: int = _DEFAULT_QUEUE_MAX,
        runtime_cfg: dict[str, Any] | None = None,
    ) -> None:
        self.capabilities: set[str] = {
            "3d",
            "external",
            "gestures",
            "gaze",
            "expressions",
        }
        self._runtime_cfg: dict[str, Any] = dict(runtime_cfg or {})
        self._transport: UnityTransport | None = transport
        self._url = url or str(self._runtime_cfg.get("url") or "ws://127.0.0.1:8765")
        self._queue: asyncio.Queue[UnityFrame] = asyncio.Queue(maxsize=queue_max)
        self._sender_task: asyncio.Task[None] | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._closed: bool = False
        self._warned_queue_full: bool = False
        self._connecting: bool = False
        self._character_id: str | None = None

        # Surfaces useful in tests / future bus integration.
        self.acks_received: int = 0
        self.telemetry_received: list[dict[str, Any]] = []

    # ----------------------------------------------------------------- API

    async def load_character(self, character_id: str, config: dict[str, Any]) -> None:
        """Tell Unity to load a character. Stores the id for later
        replay on reconnect / runtime swap."""
        self._character_id = character_id
        merged_cfg = dict(self._runtime_cfg)
        if isinstance(config, dict):
            merged_cfg.update(config)
        asset_url = (
            config.get("asset_url")
            or merged_cfg.get("asset_url")
            or self._runtime_cfg.get("asset_url")
        )
        frame: UnityFrame = {
            "type": "load.character",
            "id": character_id,
            "asset_url": asset_url,
        }
        await self._ensure_started()
        self._enqueue(frame)

    async def apply_directive(self, directive: AvatarDirective) -> None:
        await self._ensure_started()
        frame: UnityFrame = {
            "type": "avatar.directive",
            "runtime": "unity",
            "directive": directive.model_dump(mode="json"),
        }
        self._enqueue(frame)

    async def set_text(self, text: str) -> None:
        await self._ensure_started()
        self._enqueue({"type": "bubble.text", "text": text, "complete": True})

    async def start_speaking(self, text: str | None = None) -> None:
        await self._ensure_started()
        self._enqueue(
            {"type": "avatar.directive", "runtime": "unity", "speaking": True, "text": text}
        )

    async def stop_speaking(self) -> None:
        await self._ensure_started()
        self._enqueue(
            {"type": "avatar.directive", "runtime": "unity", "speaking": False}
        )

    async def set_visibility(self, visible: bool) -> None:
        await self._ensure_started()
        self._enqueue({"type": "set.visibility", "visible": visible})

    async def healthcheck(self) -> bool:
        if self._closed:
            return False
        if self._transport is None:
            return False
        return bool(self._transport.is_open)

    async def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        for task in (self._sender_task, self._reader_task):
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        self._sender_task = None
        self._reader_task = None
        if self._transport is not None:
            with contextlib.suppress(Exception):
                await self._transport.aclose()

    # --------------------------------------------------------------- internals

    async def _ensure_started(self) -> None:
        if self._closed:
            raise RuntimeError("UnityAvatarAdapter is closed")
        if self._sender_task is None or self._sender_task.done():
            self._sender_task = asyncio.create_task(
                self._sender_loop(), name="openmimicry.avatar.unity.sender"
            )
        if self._reader_task is None or self._reader_task.done():
            self._reader_task = asyncio.create_task(
                self._reader_loop(), name="openmimicry.avatar.unity.reader"
            )

    def _enqueue(self, frame: UnityFrame) -> None:
        try:
            self._queue.put_nowait(frame)
            return
        except asyncio.QueueFull:
            pass
        # Drop oldest with a one-shot warning, then make room.
        with contextlib.suppress(asyncio.QueueEmpty):
            self._queue.get_nowait()
        if not self._warned_queue_full:
            self._warned_queue_full = True
            _log.warning(
                "UnityAvatarAdapter: outbound queue full (maxsize=%d); "
                "dropping oldest frame. Is Unity reachable at %s?",
                self._queue.maxsize,
                self._url,
            )
        with contextlib.suppress(asyncio.QueueFull):
            self._queue.put_nowait(frame)

    async def _sender_loop(self) -> None:
        while not self._closed:
            try:
                await self._ensure_connected()
            except UnityTransportUnavailable as exc:
                # Optional dep missing: fail loudly *once* and stop the loop.
                _log.warning("UnityAvatarAdapter: %s", exc)
                return
            except UnityTransportError as exc:
                _log.info("UnityAvatarAdapter: transport not ready: %s", exc)
                await asyncio.sleep(self._backoff_delay())
                continue

            frame = await self._queue.get()
            transport = self._transport
            if transport is None:
                continue
            try:
                await transport.send(frame)
            except UnityTransportError as exc:
                _log.info(
                    "UnityAvatarAdapter: send failed, will reconnect: %s", exc
                )
                # Re-queue the frame at the front so it isn't lost.
                with contextlib.suppress(asyncio.QueueFull):
                    self._queue.put_nowait(frame)
                with contextlib.suppress(Exception):
                    await transport.aclose()
                self._transport = None
                await asyncio.sleep(self._backoff_delay())
            except Exception as exc:  # noqa: BLE001
                _log.warning(
                    "UnityAvatarAdapter: unexpected send error: %s", exc, exc_info=True
                )
                await asyncio.sleep(self._backoff_delay())

    async def _reader_loop(self) -> None:
        while not self._closed:
            transport = self._transport
            if transport is None or not transport.is_open:
                await asyncio.sleep(0.05)
                continue
            try:
                async for frame in transport.incoming():
                    self._consume_reverse(frame)
            except UnityTransportError as exc:
                _log.info("UnityAvatarAdapter: reader transport error: %s", exc)
            except Exception as exc:  # noqa: BLE001
                _log.warning(
                    "UnityAvatarAdapter: reader crashed: %s", exc, exc_info=True
                )
            # When the iterator ends, wait for the next reconnect.
            await asyncio.sleep(0.05)

    def _consume_reverse(self, frame: UnityFrame) -> None:
        kind = str(frame.get("type") or "")
        if kind == "ack":
            self.acks_received += 1
        elif kind == "telemetry":
            self.telemetry_received.append(dict(frame))
        else:
            _log.debug("UnityAvatarAdapter: unknown reverse frame %r", kind)

    async def _ensure_connected(self) -> None:
        if self._transport is not None and self._transport.is_open:
            return
        if self._connecting:
            return
        self._connecting = True
        try:
            transport = self._transport
            if transport is None:
                transport = self._build_default_transport()
            await transport.connect()
            self._transport = transport
        finally:
            self._connecting = False

    def _build_default_transport(self) -> UnityTransport:
        return WSUnityTransport(self._url)

    def _backoff_delay(self) -> float:
        # Single accumulator so the loop ramps up.
        # Doubling per consecutive failure, capped.
        prev = getattr(self, "_backoff_s", _INITIAL_BACKOFF_S)
        next_s = min(_MAX_BACKOFF_S, max(_INITIAL_BACKOFF_S, prev * 2))
        self._backoff_s = next_s  # type: ignore[attr-defined]
        return next_s

    # Exposed for tests + the contract suite.
    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def transport(self) -> UnityTransport | None:
        return self._transport


def make_unity_avatar_adapter(*_args: Any, **_kwargs: Any) -> UnityAvatarAdapter:
    """Entry-point factory used by the contract conftest.

    Builds the adapter with a :class:`MockUnityTransport` so the
    contract suite can exercise the full Protocol surface without
    actually talking to a Unity process.
    """
    return UnityAvatarAdapter(transport=MockUnityTransport())
