"""Scripted MockTaskRuntimeAdapter — the canonical fixture.

Replaces the Phase 0 NotImplementedError stub. Every consumer (M6 backend
integration tests, the contract suite, and end-to-end demos) drives this
mock instead of spawning real subprocesses.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any, ClassVar

from openmimicry.core.schemas.tasks import (
    TaskHandle,
    TaskRequest,
    TaskResult,
    TaskStatus,
    TaskUpdate,
)

__all__ = ["MockTaskRuntimeAdapter", "make_mock_task_runtime_adapter"]


_log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class _MockTask:
    __slots__ = (
        "cancelled",
        "handle",
        "last_note",
        "last_status",
        "producer",
        "queue",
        "request",
    )

    def __init__(
        self,
        *,
        handle: TaskHandle,
        request: TaskRequest,
        queue: asyncio.Queue,
    ) -> None:
        self.handle = handle
        self.request = request
        self.queue = queue
        self.producer: asyncio.Task | None = None
        self.cancelled: bool = False
        self.last_status: str = "queued"
        self.last_note: str | None = None


class MockTaskRuntimeAdapter:
    """Scripted TaskRuntimeAdapter — drives all integration tests."""

    name: str = "mock"
    capabilities: ClassVar[set[str]] = {"mock", "shell", "text"}

    def __init__(
        self,
        *,
        scripted_updates: list[TaskUpdate] | None = None,
        final_result: TaskResult | None = None,
        step_delay_s: float = 0.005,
    ) -> None:
        self._scripted: list[TaskUpdate] = list(scripted_updates or [])
        self._final_result_override = final_result
        self._step_delay_s = step_delay_s
        self._handles: dict[str, _MockTask] = {}
        self._closed: bool = False

    async def submit(self, req: TaskRequest) -> TaskHandle:
        handle = TaskHandle(id=str(uuid.uuid4()), runtime=self.name)
        task = _MockTask(handle=handle, request=req, queue=asyncio.Queue(maxsize=64))
        self._handles[handle.id] = task
        task.producer = asyncio.create_task(
            self._produce(task), name=f"openmimicry.tasks.mock.{handle.id}"
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
        if t.producer is not None and not t.producer.done():
            t.producer.cancel()
        upd = TaskUpdate(handle=handle, status="cancelled", ts=_now())
        try:
            t.queue.put_nowait(upd)
        except asyncio.QueueFull:
            pass
        t.queue.put_nowait(None)  # sentinel
        t.last_status = "cancelled"

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
        if t.producer is not None:
            try:
                await t.producer
            except asyncio.CancelledError:
                pass
        if self._final_result_override is not None:
            return self._final_result_override.model_copy(update={"handle": handle})
        return TaskResult(handle=handle, status=t.last_status)

    async def healthcheck(self) -> bool:
        return not self._closed

    async def _produce(self, t: _MockTask) -> None:
        try:
            for raw in self._scripted:
                if t.cancelled:
                    return
                upd = raw.model_copy(update={"handle": t.handle, "ts": _now()})
                t.last_status = upd.status
                t.last_note = upd.note
                await t.queue.put(upd)
                if self._step_delay_s > 0:
                    await asyncio.sleep(self._step_delay_s)
            if not self._scripted or self._scripted[-1].status not in {
                "succeeded",
                "failed",
                "cancelled",
            }:
                final = TaskUpdate(handle=t.handle, status="succeeded", ts=_now())
                t.last_status = "succeeded"
                await t.queue.put(final)
            await t.queue.put(None)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "MockTaskRuntimeAdapter producer crashed: %s", exc, exc_info=True
            )
            await t.queue.put(None)


def make_mock_task_runtime_adapter(*_args: Any, **_kwargs: Any) -> MockTaskRuntimeAdapter:
    """Factory used by the contract conftest."""
    return MockTaskRuntimeAdapter()
