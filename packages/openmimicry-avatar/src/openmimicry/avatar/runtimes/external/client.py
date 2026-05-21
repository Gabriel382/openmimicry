"""Generic external-renderer WS client.

Same split as M11's transport layer but with no Unity-specific
knowledge. ``ExternalClient`` is a runtime-checkable Protocol;
``WSExternalClient`` is the real implementation (lazy-imports
``websockets``); ``MockExternalClient`` is the test fixture that
records sent frames and lets tests push the reverse channel.

Wire-protocol shapes are defined in
``docs/modules/post_v0_2_modalities.md`` (M12 section).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "ExternalClient",
    "ExternalClientError",
    "ExternalFrame",
    "ExternalUnavailable",
    "MockExternalClient",
    "WSExternalClient",
]


_log = logging.getLogger(__name__)


ExternalFrame = dict[str, Any]


class ExternalClientError(RuntimeError):
    """Raised by clients on send/recv errors. Callers reconnect."""


class ExternalUnavailable(RuntimeError):
    """Raised when the WS client requirements aren't met (missing
    `websockets` extra)."""


@runtime_checkable
class ExternalClient(Protocol):
    """Minimal async client interface used by ``ExternalAvatarAdapter``."""

    async def connect(self) -> None: ...

    async def send(self, frame: ExternalFrame) -> None: ...

    async def aclose(self) -> None: ...

    def incoming(self) -> AsyncIterator[ExternalFrame]: ...

    @property
    def is_open(self) -> bool: ...


# ---------------------------------------------------------------------------
# MockExternalClient
# ---------------------------------------------------------------------------


class MockExternalClient:
    """Deterministic client used by tests + the contract suite.

    Records every :meth:`send` in :attr:`sent_frames`. Tests drive the
    reverse channel via :meth:`feed_incoming` (third-party renderer ->
    backend frames such as ``{"type":"ack",...}``, ``{"type":"ready"}``,
    ``{"type":"error", ...}``).
    """

    def __init__(self, *, fail_until_attempt: int = 0) -> None:
        self.sent_frames: list[ExternalFrame] = []
        self._incoming: asyncio.Queue[ExternalFrame | None] = asyncio.Queue()
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
            raise ExternalClientError("client closed")
        if self._connect_attempts <= self._fail_until:
            raise ExternalClientError(
                f"mock client refused connect (attempt={self._connect_attempts})"
            )
        self._open = True

    async def send(self, frame: ExternalFrame) -> None:
        if not self._open:
            raise ExternalClientError("send while client not open")
        self.sent_frames.append(dict(frame))

    async def aclose(self) -> None:
        self._closed = True
        self._open = False
        await self._incoming.put(None)

    def incoming(self) -> AsyncIterator[ExternalFrame]:
        return self._iter_incoming()

    async def _iter_incoming(self) -> AsyncIterator[ExternalFrame]:
        while True:
            item = await self._incoming.get()
            if item is None:
                return
            yield item

    # ----- test-only hooks ---------------------------------------------------

    async def feed_incoming(self, frame: ExternalFrame) -> None:
        await self._incoming.put(dict(frame))

    def simulate_disconnect(self) -> None:
        self._open = False


# ---------------------------------------------------------------------------
# WSExternalClient
# ---------------------------------------------------------------------------


class WSExternalClient:
    """Real WebSocket client. ``websockets`` is lazy-imported.

    The adapter owns the reconnect loop + bounded queue; this client
    only knows how to talk to one socket at a time.
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
        mod = _import_websockets()
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
            raise ExternalClientError(
                f"external WS connect timed out for {self._url}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise ExternalClientError(f"external WS connect failed: {exc}") from exc
        self._open = True

    async def send(self, frame: ExternalFrame) -> None:
        ws = self._ws
        if ws is None or not self._open:
            raise ExternalClientError("send while client not open")
        payload = json.dumps(frame, default=str)
        try:
            await asyncio.wait_for(ws.send(payload), timeout=self._send_timeout_s)
        except asyncio.TimeoutError as exc:
            raise ExternalClientError("external WS send timed out") from exc
        except Exception as exc:  # noqa: BLE001
            self._open = False
            raise ExternalClientError(f"external WS send failed: {exc}") from exc

    async def aclose(self) -> None:
        ws = self._ws
        self._ws = None
        self._open = False
        if ws is None:
            return
        try:
            await ws.close()
        except Exception as exc:  # noqa: BLE001
            _log.debug("WSExternalClient close raised: %s", exc)

    def incoming(self) -> AsyncIterator[ExternalFrame]:
        return self._iter_incoming()

    async def _iter_incoming(self) -> AsyncIterator[ExternalFrame]:
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
                    _log.warning(
                        "WSExternalClient: dropped malformed frame: %s", exc
                    )
                    continue
        except Exception as exc:  # noqa: BLE001
            _log.info("WSExternalClient: incoming() ended: %s", exc)
            self._open = False
            return


def _import_websockets() -> Any:
    """Lazy-import ``websockets`` with a typed error on failure."""
    try:
        import websockets  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ExternalUnavailable(
            "websockets is not installed. Install with "
            "`pip install \"openmimicry-avatar[external]\"`."
        ) from exc
    return websockets
