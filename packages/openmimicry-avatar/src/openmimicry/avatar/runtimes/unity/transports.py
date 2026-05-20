"""Pluggable transports for the Unity bridge.

The adapter only talks to a transport; concrete classes own the
protocol detail. Two shipped transports:

* :class:`WSUnityTransport` — opens a WebSocket to the configured
  endpoint. ``websockets`` is lazy-imported so a pure mocks-only install
  doesn't drag it in.
* :class:`MockUnityTransport` — records every sent frame in
  ``sent_frames`` and lets tests push reverse-channel frames via
  :meth:`feed_incoming`.

All sends + receives are JSON-encoded ``dict``s. The shape is the
additive wire-protocol amendment documented in
``docs/modules/post_v0_2_modalities.md`` (M11 section).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "MockUnityTransport",
    "UnityFrame",
    "UnityTransport",
    "UnityTransportError",
    "UnityTransportUnavailable",
    "WSUnityTransport",
]


_log = logging.getLogger(__name__)


UnityFrame = dict[str, Any]


class UnityTransportError(RuntimeError):
    """Raised by transports on send/recv errors. Callers reconnect."""


class UnityTransportUnavailable(RuntimeError):
    """Raised when the WebSocket transport requirements aren't met
    (e.g. the optional `websockets` package is missing)."""


@runtime_checkable
class UnityTransport(Protocol):
    """Minimal async transport interface."""

    async def connect(self) -> None: ...

    async def send(self, frame: UnityFrame) -> None: ...

    async def aclose(self) -> None: ...

    def incoming(self) -> AsyncIterator[UnityFrame]: ...

    @property
    def is_open(self) -> bool: ...


# ---------------------------------------------------------------------------
# MockUnityTransport
# ---------------------------------------------------------------------------


class MockUnityTransport:
    """Deterministic transport used by the unit + contract tests.

    Records every :meth:`send` call into :attr:`sent_frames`. Tests drive
    the reverse channel via :meth:`feed_incoming` (server -> backend
    frames such as ``{"type":"ack",...}``).
    """

    def __init__(self, *, fail_until_attempt: int = 0) -> None:
        self.sent_frames: list[UnityFrame] = []
        self._incoming: asyncio.Queue[UnityFrame | None] = asyncio.Queue()
        self._open: bool = False
        self._connect_attempts: int = 0
        self._fail_until = fail_until_attempt
        self._closed: bool = False

    @property
    def is_open(self) -> bool:
        return self._open

    async def connect(self) -> None:
        self._connect_attempts += 1
        if self._closed:
            raise UnityTransportError("transport closed")
        if self._connect_attempts <= self._fail_until:
            raise UnityTransportError(
                f"mock transport refused connect (attempt={self._connect_attempts})"
            )
        self._open = True

    async def send(self, frame: UnityFrame) -> None:
        if not self._open:
            raise UnityTransportError("send while transport not open")
        self.sent_frames.append(dict(frame))

    async def aclose(self) -> None:
        self._closed = True
        self._open = False
        await self._incoming.put(None)  # sentinel for any iterator

    def incoming(self) -> AsyncIterator[UnityFrame]:
        return self._iter_incoming()

    async def _iter_incoming(self) -> AsyncIterator[UnityFrame]:
        while True:
            item = await self._incoming.get()
            if item is None:
                return
            yield item

    # ----- test-only hooks ---------------------------------------------------

    async def feed_incoming(self, frame: UnityFrame) -> None:
        """Push a frame as if Unity sent it."""
        await self._incoming.put(dict(frame))

    def simulate_disconnect(self) -> None:
        """Flip ``is_open`` to False so the next :meth:`send` raises."""
        self._open = False


# ---------------------------------------------------------------------------
# WSUnityTransport
# ---------------------------------------------------------------------------


class WSUnityTransport:
    """WebSocket transport. ``websockets`` is lazy-imported.

    The transport itself does not retry; the :class:`UnityAvatarAdapter`
    owns the reconnect loop + bounded queue. This keeps the transport's
    surface small and easy to mock.
    """

    def __init__(
        self,
        url: str,
        *,
        connect_timeout_s: float = 5.0,
        send_timeout_s: float = 2.0,
        ping_interval_s: float | None = 20.0,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self._url = url
        self._connect_timeout_s = connect_timeout_s
        self._send_timeout_s = send_timeout_s
        self._ping_interval_s = ping_interval_s
        self._extra_headers = dict(extra_headers or {})
        self._ws: Any = None
        self._open: bool = False

    @property
    def is_open(self) -> bool:
        return self._open and self._ws is not None

    async def connect(self) -> None:
        try:
            mod = _import_websockets()
        except UnityTransportUnavailable:
            raise
        try:
            self._ws = await asyncio.wait_for(
                mod.connect(
                    self._url,
                    ping_interval=self._ping_interval_s,
                    additional_headers=list(self._extra_headers.items()) or None,
                ),
                timeout=self._connect_timeout_s,
            )
        except asyncio.TimeoutError as exc:
            raise UnityTransportError(f"WS connect timed out for {self._url}") from exc
        except Exception as exc:  # noqa: BLE001
            raise UnityTransportError(f"WS connect failed: {exc}") from exc
        self._open = True

    async def send(self, frame: UnityFrame) -> None:
        ws = self._ws
        if ws is None or not self._open:
            raise UnityTransportError("send while transport not open")
        payload = json.dumps(frame, default=str)
        try:
            await asyncio.wait_for(ws.send(payload), timeout=self._send_timeout_s)
        except asyncio.TimeoutError as exc:
            raise UnityTransportError("WS send timed out") from exc
        except Exception as exc:  # noqa: BLE001
            self._open = False
            raise UnityTransportError(f"WS send failed: {exc}") from exc

    async def aclose(self) -> None:
        ws = self._ws
        self._ws = None
        self._open = False
        if ws is None:
            return
        try:
            await ws.close()
        except Exception as exc:  # noqa: BLE001
            _log.debug("WSUnityTransport close raised: %s", exc)

    def incoming(self) -> AsyncIterator[UnityFrame]:
        return self._iter_incoming()

    async def _iter_incoming(self) -> AsyncIterator[UnityFrame]:
        ws = self._ws
        if ws is None:
            return
        try:
            async for raw in ws:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                try:
                    yield json.loads(raw)
                except json.JSONDecodeError as exc:
                    _log.warning("WSUnityTransport: dropped malformed frame: %s", exc)
                    continue
        except Exception as exc:  # noqa: BLE001
            _log.info("WSUnityTransport: incoming() ended: %s", exc)
            self._open = False
            return


def _import_websockets() -> Any:
    """Lazy-import ``websockets`` with a typed error on failure."""
    try:
        import websockets  # type: ignore[import-not-found]
    except ImportError as exc:
        raise UnityTransportUnavailable(
            "websockets is not installed. Install with "
            "`pip install \"openmimicry-avatar[unity]\"`."
        ) from exc
    return websockets
