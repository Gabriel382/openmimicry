"""``MCPAgentAdapter`` — bridges to the ``mcp-agent`` library.

``mcp-agent`` is heavy and lazy-imported inside :meth:`submit` /
:meth:`healthcheck` so a pure-mock install (the default) doesn't pay the
cost. If the extra isn't installed, we raise :class:`MCPAgentUnavailable`
with a clean pointer to the install command.

The translation is intentionally minimal: every event the mcp-agent run
emits becomes a :class:`TaskUpdate` with the event's payload in
``note``. M6 can subscribe to the events and project them to richer
shapes if needed.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar

from openmimicry.core.schemas.tasks import (
    TaskError,
    TaskHandle,
    TaskRequest,
    TaskResult,
    TaskStatus,
    TaskUpdate,
)

__all__ = [
    "MCPAgentAdapter",
    "MCPAgentSettings",
    "MCPAgentUnavailable",
    "make_mcp_agent_adapter",
]


_log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MCPAgentUnavailable(RuntimeError):
    """Raised when ``mcp-agent`` is not installed."""


@dataclass(frozen=True)
class MCPAgentServerConfig:
    name: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class MCPAgentSettings:
    servers: tuple[MCPAgentServerConfig, ...] = ()
    queue_maxsize: int = 256
    extra: dict[str, Any] = field(default_factory=dict)


class _MCPTask:
    __slots__ = (
        "cancelled",
        "handle",
        "last_note",
        "last_status",
        "queue",
        "request",
        "run_handle",
        "task",
    )

    def __init__(self, handle: TaskHandle, request: TaskRequest, queue: asyncio.Queue) -> None:
        self.handle = handle
        self.request = request
        self.queue = queue
        self.run_handle: Any = None
        self.cancelled: bool = False
        self.last_status: str = "queued"
        self.last_note: str | None = None
        self.task: asyncio.Task | None = None


class MCPAgentAdapter:
    """TaskRuntimeAdapter backed by ``mcp-agent``."""

    name: str = "mcp_agent"
    capabilities: ClassVar[set[str]] = {"mcp", "text"}

    def __init__(self, *, settings: MCPAgentSettings | None = None) -> None:
        self._settings = settings or MCPAgentSettings()
        self._handles: dict[str, _MCPTask] = {}
        self._closed: bool = False

    # ----------------------------------------------------------------- API

    async def submit(self, req: TaskRequest) -> TaskHandle:
        # Surface the install error early if the extra is missing.
        try:
            _import_mcp_agent()
        except MCPAgentUnavailable as exc:
            handle = TaskHandle(id=str(uuid.uuid4()), runtime=self.name)
            queue: asyncio.Queue = asyncio.Queue(maxsize=self._settings.queue_maxsize)
            t = _MCPTask(handle=handle, request=req, queue=queue)
            self._handles[handle.id] = t
            t.last_status = "failed"
            t.last_note = str(exc)
            await queue.put(
                TaskUpdate(
                    handle=handle,
                    status="failed",
                    ts=_now(),
                    error=TaskError(code="mcp_agent_missing", message=str(exc)),
                )
            )
            await queue.put(None)
            return handle

        handle = TaskHandle(id=str(uuid.uuid4()), runtime=self.name)
        queue = asyncio.Queue(maxsize=self._settings.queue_maxsize)
        t = _MCPTask(handle=handle, request=req, queue=queue)
        self._handles[handle.id] = t
        t.task = asyncio.create_task(
            self._run(t), name=f"openmimicry.tasks.mcp.{handle.id}"
        )
        return handle

    async def status(self, handle: TaskHandle) -> TaskStatus:
        t = self._handles.get(handle.id)
        if t is None:
            return TaskStatus(handle=handle, status="failed", note="unknown handle")
        return TaskStatus(handle=handle, status=t.last_status, note=t.last_note)

    async def cancel(self, handle: TaskHandle) -> None:
        t = self._handles.get(handle.id)
        if t is None:
            return
        t.cancelled = True
        rh = t.run_handle
        if rh is not None:
            cancel = getattr(rh, "cancel", None)
            if callable(cancel):
                try:
                    res = cancel()
                    if asyncio.iscoroutine(res):
                        await res
                except Exception:  # noqa: BLE001
                    pass
        if t.task is not None and not t.task.done():
            t.task.cancel()

    def updates(self, handle: TaskHandle) -> AsyncIterator[TaskUpdate]:
        return self._iter_updates(handle)

    async def _iter_updates(self, handle: TaskHandle) -> AsyncIterator[TaskUpdate]:
        t = self._handles.get(handle.id)
        if t is None:
            return
        while True:
            item = await t.queue.get()
            if item is None:
                return
            yield item

    async def result(self, handle: TaskHandle) -> TaskResult:
        t = self._handles.get(handle.id)
        if t is None:
            return TaskResult(handle=handle, status="failed")
        if t.task is not None:
            try:
                await t.task
            except asyncio.CancelledError:
                pass
        if t.cancelled:
            return TaskResult(handle=handle, status="cancelled")
        if t.last_status == "failed":
            return TaskResult(
                handle=handle,
                status="failed",
                error=TaskError(code="mcp_run_failed", message=t.last_note or "failed"),
            )
        return TaskResult(handle=handle, status="succeeded")

    async def healthcheck(self) -> bool:
        if self._closed:
            return False
        try:
            _import_mcp_agent()
        except MCPAgentUnavailable:
            return False
        return True

    # --------------------------------------------------------------- runner

    async def _run(self, t: _MCPTask) -> None:
        try:
            mcp = _import_mcp_agent()
            agent_cls = getattr(mcp, "Agent", None)
            if agent_cls is None:
                raise MCPAgentUnavailable("mcp_agent exposes no Agent class")

            # Construct the agent. The exact constructor surface differs
            # across mcp-agent versions; we pass kwargs the brief listed
            # and let unknown ones be tolerated by setattr fallback.
            agent = agent_cls(
                instructions=t.request.instructions,
                servers=[
                    {"name": s.name, "command": list(s.command)}
                    for s in self._settings.servers
                ],
            )
            t.run_handle = agent
            t.last_status = "running"
            await self._offer(
                t.queue,
                TaskUpdate(handle=t.handle, status="running", ts=_now()),
            )

            # Iterate over the run's event stream. We accept either
            # `agent.run()` returning an async iterator OR an async method
            # returning a final result; both shapes appear across versions.
            run = getattr(agent, "run", None)
            if run is None:
                raise MCPAgentUnavailable("mcp_agent.Agent has no run() method")
            result = run()
            if hasattr(result, "__aiter__"):
                async for event in result:
                    note = _event_note(event)
                    await self._offer(
                        t.queue,
                        TaskUpdate(
                            handle=t.handle, status="running", ts=_now(), note=note
                        ),
                    )
            else:
                final = await result if asyncio.iscoroutine(result) else result
                note = _event_note(final)
                await self._offer(
                    t.queue,
                    TaskUpdate(handle=t.handle, status="running", ts=_now(), note=note),
                )

            if t.cancelled:
                t.last_status = "cancelled"
                await self._offer(
                    t.queue, TaskUpdate(handle=t.handle, status="cancelled", ts=_now())
                )
            else:
                t.last_status = "succeeded"
                await self._offer(
                    t.queue, TaskUpdate(handle=t.handle, status="succeeded", ts=_now())
                )
        except asyncio.CancelledError:
            t.cancelled = True
            await self._offer(
                t.queue, TaskUpdate(handle=t.handle, status="cancelled", ts=_now())
            )
            raise
        except Exception as exc:  # noqa: BLE001
            t.last_status = "failed"
            t.last_note = str(exc)
            _log.warning("MCPAgentAdapter run failed: %s", exc, exc_info=True)
            await self._offer(
                t.queue,
                TaskUpdate(
                    handle=t.handle,
                    status="failed",
                    ts=_now(),
                    error=TaskError(code="mcp_run_failed", message=str(exc)),
                ),
            )
        finally:
            await self._offer(t.queue, None)

    async def _offer(self, queue: asyncio.Queue, item: Any) -> None:
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(item)
            except asyncio.QueueFull:
                _log.warning("MCPAgentAdapter: update queue full; dropping update")


def _event_note(event: Any) -> str:
    """Best-effort string projection of an mcp-agent event."""
    if event is None:
        return ""
    if isinstance(event, str):
        return event
    for attr in ("note", "message", "text", "summary"):
        value = getattr(event, attr, None)
        if isinstance(value, str) and value:
            return value
    try:
        return repr(event)[:256]
    except Exception:  # noqa: BLE001
        return "<event>"


def _import_mcp_agent() -> Any:
    """Lazy-import ``mcp_agent`` with a typed error on failure."""
    try:
        import mcp_agent  # type: ignore[import-not-found]
    except ImportError as exc:
        raise MCPAgentUnavailable(
            "mcp-agent is not installed. "
            'Install with `pip install "openmimicry-tasks[mcp-agent]"`.'
        ) from exc
    return mcp_agent


def make_mcp_agent_adapter(*_args: Any, **_kwargs: Any) -> MCPAgentAdapter:
    """Factory used by the contract conftest."""
    return MCPAgentAdapter()
