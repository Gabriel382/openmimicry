"""``ExternalAvatarAdapter`` — generic third-party-renderer bridge.

Same shape as :class:`UnityAvatarAdapter` but renderer-agnostic. Pushes
``avatar.directive`` / ``load.character`` / ``set.visibility`` /
``set.text`` / ``shutdown`` frames to whatever the
``ExternalClient`` is pointed at. Reverse channel: ``ack`` / ``ready``
/ ``error``.

See ``docs/external_runtimes.md`` for two worked-example renderers
(Unity-flavour, browser-flavour) and the wire-protocol spec.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from openmimicry.core.schemas import AvatarDirective

from .client import (
    ExternalClient,
    ExternalClientError,
    ExternalFrame,
    ExternalUnavailable,
    MockExternalClient,
    WSExternalClient,
)

__all__ = [
    "ExternalAvatarAdapter",
    "ExternalUnavailable",
    "make_external_avatar_adapter",
]


_log = logging.getLogger(__name__)


_INITIAL_BACKOFF_S: float = 0.25
_MAX_BACKOFF_S: float = 5.0
_DEFAULT_QUEUE_MAX: int = 64


class ExternalAvatarAdapter:
    """Concrete :class:`AvatarRuntimeAdapter` for external renderers."""

    name: str = "external"

    def __init__(
        self,
        *,
        client: ExternalClient | None = None,
        url: str | None = None,
        queue_max: int = _DEFAULT_QUEUE_MAX,
        runtime_cfg: dict[str, Any] | None = None,
    ) -> None:
        # Capability `"external"` advertises the modality; the rest are
        # the directive fields a compliant renderer is expected to
        # honour. Renderers can ignore any unsupported field — same
        # rule as M9/M11.
        self.capabilities: set[str] = {
            "external",
            "gestures",
            "gaze",
            "expressions",
        }
        self._runtime_cfg: dict[str, Any] = dict(runtime_cfg or {})
        self._client: ExternalClient | None = client
        self._url = url or str(
            self._runtime_cfg.get("url") or "ws://127.0.0.1:8765"
        )
        self._queue: asyncio.Queue[ExternalFrame] = asyncio.Queue(maxsize=queue_max)
        self._sender_task: asyncio.Task[None] | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._closed: bool = False
        self._warned_queue_full: bool = False
        self._connecting: bool = False
        self._character_id: str | None = None

        # Reverse-channel state surfaced to tests / future bus integration.
        self.acks_received: int = 0
        self.ready_received: int = 0
        self.errors_received: list[dict[str, Any]] = []

    # ----------------------------------------------------------------- API

    async def load_character(self, character_id: str, config: dict[str, Any]) -> None:
        self._character_id = character_id
        merged_cfg = dict(self._runtime_cfg)
        if isinstance(config, dict):
            merged_cfg.update(config)
        asset_url = (
            config.get("asset_url")
            or merged_cfg.get("asset_url")
            or self._runtime_cfg.get("asset_url")
        )
        frame: ExternalFrame = {
            "type": "load.character",
            "id": character_id,
            "asset_url": asset_url,
        }
        await self._ensure_started()
        self._enqueue(frame)

    async def apply_directive(self, directive: AvatarDirective) -> None:
        await self._ensure_started()
        frame: ExternalFrame = {
            "type": "avatar.directive",
            "runtime": "external",
            "directive": directive.model_dump(mode="json"),
        }
        self._enqueue(frame)

    async def set_text(self, text: str) -> None:
        await self._ensure_started()
        self._enqueue({"type": "set.text", "text": text})

    async def start_speaking(self, text: str | None = None) -> None:
        await self._ensure_started()
        self._enqueue(
            {
                "type": "avatar.directive",
                "runtime": "external",
                "speaking": True,
                "text": text,
            }
        )

    async def stop_speaking(self) -> None:
        await self._ensure_started()
        self._enqueue(
            {"type": "avatar.directive", "runtime": "external", "speaking": False}
        )

    async def set_visibility(self, visible: bool) -> None:
        await self._ensure_started()
        self._enqueue({"type": "set.visibility", "visible": visible})

    async def healthcheck(self) -> bool:
        if self._closed:
            return False
        if self._client is None:
            return False
        return bool(self._client.is_open)

    async def shutdown(self) -> None:
        if self._closed:
            return
        # Send a polite shutdown frame so the renderer can clean up
        # (best-effort; we swallow errors).
        client = self._client
        if client is not None and client.is_open:
            with contextlib.suppress(Exception):
                await client.send({"type": "shutdown"})
        self._closed = True
        for task in (self._sender_task, self._reader_task):
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        self._sender_task = None
        self._reader_task = None
        if self._client is not None:
            with contextlib.suppress(Exception):
                await self._client.aclose()

    # --------------------------------------------------------------- internals

    async def _ensure_started(self) -> None:
        if self._closed:
            raise RuntimeError("ExternalAvatarAdapter is closed")
        if self._sender_task is None or self._sender_task.done():
            self._sender_task = asyncio.create_task(
                self._sender_loop(), name="openmimicry.avatar.external.sender"
            )
        if self._reader_task is None or self._reader_task.done():
            self._reader_task = asyncio.create_task(
                self._reader_loop(), name="openmimicry.avatar.external.reader"
            )

    def _enqueue(self, frame: ExternalFrame) -> None:
        try:
            self._queue.put_nowait(frame)
            return
        except asyncio.QueueFull:
            pass
        with contextlib.suppress(asyncio.QueueEmpty):
            self._queue.get_nowait()
        if not self._warned_queue_full:
            self._warned_queue_full = True
            _log.warning(
                "ExternalAvatarAdapter: outbound queue full (maxsize=%d); "
                "dropping oldest frame. Is the renderer reachable at %s?",
                self._queue.maxsize,
                self._url,
            )
        with contextlib.suppress(asyncio.QueueFull):
            self._queue.put_nowait(frame)

    async def _sender_loop(self) -> None:
        while not self._closed:
            try:
                await self._ensure_connected()
            except ExternalUnavailable as exc:
                _log.warning("ExternalAvatarAdapter: %s", exc)
                return
            except ExternalClientError as exc:
                _log.info("ExternalAvatarAdapter: client not ready: %s", exc)
                await asyncio.sleep(self._backoff_delay())
                continue

            frame = await self._queue.get()
            client = self._client
            if client is None:
                continue
            try:
                await client.send(frame)
            except ExternalClientError as exc:
                _log.info(
                    "ExternalAvatarAdapter: send failed, will reconnect: %s", exc
                )
                with contextlib.suppress(asyncio.QueueFull):
                    self._queue.put_nowait(frame)
                with contextlib.suppress(Exception):
                    await client.aclose()
                self._client = None
                await asyncio.sleep(self._backoff_delay())
            except Exception as exc:  # noqa: BLE001
                _log.warning(
                    "ExternalAvatarAdapter: unexpected send error: %s",
                    exc,
                    exc_info=True,
                )
                await asyncio.sleep(self._backoff_delay())

    async def _reader_loop(self) -> None:
        while not self._closed:
            client = self._client
            if client is None or not client.is_open:
                await asyncio.sleep(0.05)
                continue
            try:
                async for frame in client.incoming():
                    self._consume_reverse(frame)
            except ExternalClientError as exc:
                _log.info("ExternalAvatarAdapter: reader transport error: %s", exc)
            except Exception as exc:  # noqa: BLE001
                _log.warning(
                    "ExternalAvatarAdapter: reader crashed: %s",
                    exc,
                    exc_info=True,
                )
            await asyncio.sleep(0.05)

    def _consume_reverse(self, frame: ExternalFrame) -> None:
        kind = str(frame.get("type") or "")
        if kind == "ack":
            self.acks_received += 1
        elif kind == "ready":
            self.ready_received += 1
        elif kind == "error":
            self.errors_received.append(dict(frame))
            _log.warning(
                "ExternalAvatarAdapter: renderer reported error: %s",
                frame.get("message"),
            )
        else:
            _log.debug("ExternalAvatarAdapter: unknown reverse frame %r", kind)

    async def _ensure_connected(self) -> None:
        if self._client is not None and self._client.is_open:
            return
        if self._connecting:
            return
        self._connecting = True
        try:
            client = self._client
            if client is None:
                client = self._build_default_client()
            await client.connect()
            self._client = client
        finally:
            self._connecting = False

    def _build_default_client(self) -> ExternalClient:
        return WSExternalClient(self._url)

    def _backoff_delay(self) -> float:
        prev = getattr(self, "_backoff_s", _INITIAL_BACKOFF_S)
        next_s = min(_MAX_BACKOFF_S, max(_INITIAL_BACKOFF_S, prev * 2))
        self._backoff_s = next_s  # type: ignore[attr-defined]
        return next_s

    # Exposed for tests / panel UI.
    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def client(self) -> ExternalClient | None:
        return self._client


def make_external_avatar_adapter(*_args: Any, **_kwargs: Any) -> ExternalAvatarAdapter:
    """Entry-point factory used by the contract conftest.

    Builds the adapter with a :class:`MockExternalClient` so the
    contract suite exercises the full Protocol surface without
    actually opening a socket.
    """
    return ExternalAvatarAdapter(client=MockExternalClient())
