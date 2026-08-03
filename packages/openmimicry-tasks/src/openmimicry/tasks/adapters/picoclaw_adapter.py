"""PicoClaw one-shot task adapter.

PicoClaw remains an optional external executable.  OpenMimicry never copies
its credentials; it runs ``picoclaw agent -m <instruction>`` inside the
selected project directory and captures output through the frozen task
contract.
"""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar

from openmimicry.core.schemas.tasks import (
    TaskError,
    TaskHandle,
    TaskRequest,
    TaskResult,
    TaskStatus,
    TaskUpdate,
)

__all__ = ["PicoClawAdapter", "PicoClawSettings"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class PicoClawSettings:
    cli: str = "picoclaw"
    working_dir: str = "."
    cancel_grace_s: float = 3.0
    queue_maxsize: int = 256


class _PicoTask:
    def __init__(self, handle: TaskHandle, request: TaskRequest, maxsize: int) -> None:
        self.handle = handle
        self.request = request
        self.queue: asyncio.Queue[TaskUpdate | None] = asyncio.Queue(maxsize=maxsize)
        self.process: asyncio.subprocess.Process | None = None
        self.runner: asyncio.Task[None] | None = None
        self.status = "queued"
        self.note: str | None = None
        self.output: list[str] = []
        self.cancelled = False


class PicoClawAdapter:
    name = "picoclaw"
    capabilities: ClassVar[set[str]] = {"text", "tools", "mcp", "shell"}

    def __init__(self, *, settings: PicoClawSettings | None = None) -> None:
        self._settings = settings or PicoClawSettings()
        self._tasks: dict[str, _PicoTask] = {}

    def _cli(self) -> str:
        configured = self._settings.cli
        if "/" in configured or "\\" in configured:
            if not Path(configured).is_file():
                raise FileNotFoundError(f"PicoClaw executable not found: {configured}")
            return configured
        found = shutil.which(configured)
        if found is None:
            raise FileNotFoundError(
                "picoclaw is not on PATH; install PicoClaw or configure tasks.runtimes.picoclaw.cli"
            )
        return found

    async def submit(self, req: TaskRequest) -> TaskHandle:
        handle = TaskHandle(id=str(uuid.uuid4()), runtime=self.name)
        task = _PicoTask(handle, req, self._settings.queue_maxsize)
        self._tasks[handle.id] = task
        task.runner = asyncio.create_task(self._run(task))
        return handle

    async def _run(self, task: _PicoTask) -> None:
        try:
            cli = self._cli()
            cwd = task.request.constraints.working_dir or self._settings.working_dir
            task.process = await asyncio.create_subprocess_exec(
                cli,
                "agent",
                "-m",
                task.request.instructions,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            task.status = "running"
            await task.queue.put(
                TaskUpdate(
                    handle=task.handle,
                    status="running",
                    note="PicoClaw started",
                    ts=_now(),
                )
            )
            assert task.process.stdout is not None
            async for raw in task.process.stdout:
                line = raw.decode("utf-8", errors="replace").rstrip()
                task.output.append(line)
                await task.queue.put(
                    TaskUpdate(
                        handle=task.handle,
                        status="running",
                        stdout=line,
                        ts=_now(),
                    )
                )
            code = await task.process.wait()
            task.status = "cancelled" if task.cancelled else "succeeded" if code == 0 else "failed"
            task.note = None if code == 0 else f"PicoClaw exited with status {code}"
            await task.queue.put(
                TaskUpdate(
                    handle=task.handle,
                    status=task.status,
                    note=task.note,
                    error=(
                        TaskError(code=f"exit_{code}", message=task.note)
                        if code and not task.cancelled
                        else None
                    ),
                    ts=_now(),
                )
            )
        except Exception as exc:
            task.status = "failed"
            task.note = str(exc)
            await task.queue.put(
                TaskUpdate(
                    handle=task.handle,
                    status="failed",
                    error=TaskError(code="picoclaw_failed", message=str(exc)),
                    ts=_now(),
                )
            )
        finally:
            await task.queue.put(None)

    async def status(self, handle: TaskHandle) -> TaskStatus:
        task = self._tasks.get(handle.id)
        if task is None:
            return TaskStatus(handle=handle, status="failed", note="unknown handle")
        return TaskStatus(handle=handle, status=task.status, note=task.note)

    async def cancel(self, handle: TaskHandle) -> None:
        task = self._tasks.get(handle.id)
        if task is None or task.process is None:
            return
        task.cancelled = True
        with contextlib.suppress(ProcessLookupError):
            task.process.terminate()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(task.process.wait(), self._settings.cancel_grace_s)
            return
        with contextlib.suppress(ProcessLookupError):
            task.process.kill()

    def updates(self, handle: TaskHandle) -> AsyncIterator[TaskUpdate]:
        return self._updates(handle)

    async def _updates(self, handle: TaskHandle) -> AsyncIterator[TaskUpdate]:
        task = self._tasks.get(handle.id)
        if task is None:
            return
        while True:
            update = await task.queue.get()
            if update is None:
                return
            yield update

    async def result(self, handle: TaskHandle) -> TaskResult:
        task = self._tasks.get(handle.id)
        if task is None:
            return TaskResult(handle=handle, status="failed")
        if task.runner is not None:
            await task.runner
        return TaskResult(
            handle=handle,
            status=task.status,
            summary="\n".join(task.output).strip() or task.note,
            error=(
                TaskError(code="picoclaw_failed", message=task.note or "PicoClaw failed")
                if task.status == "failed"
                else None
            ),
        )

    async def healthcheck(self) -> bool:
        try:
            self._cli()
        except FileNotFoundError:
            return False
        return True

    async def close(self) -> None:
        for task in self._tasks.values():
            if task.runner is not None and not task.runner.done():
                await self.cancel(task.handle)
