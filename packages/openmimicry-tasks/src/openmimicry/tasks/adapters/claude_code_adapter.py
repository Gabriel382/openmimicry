"""``ClaudeCodeAdapter`` — spawns and supervises the ``claude`` CLI.

Per the M5 brief:

* Resolve the CLI from ``settings.cli`` or :func:`shutil.which("claude")`.
* Build the prompt from ``req.instructions`` (and optionally append file
  contents from ``req.inputs`` of kind ``"file"``).
* Run with a fixed ``working_dir``; do **not** inherit the parent
  environment beyond what's necessary (we pass ``env=os.environ`` minus
  noisy bits by default, but expose a hook for tests).
* Parse stdout line-by-line for ``Wrote file …``, ``Ran command …``,
  ``Error: …`` patterns and surface them via :class:`TaskUpdate.note`.
* Cancel via SIGTERM → SIGKILL after ``cancel_grace_s``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shlex
import shutil
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar

from openmimicry.core.schemas.tasks import (
    Artifact,
    TaskError,
    TaskHandle,
    TaskRequest,
    TaskResult,
    TaskStatus,
    TaskUpdate,
)

__all__ = [
    "ClaudeCodeAdapter",
    "ClaudeCodeSettings",
    "ClaudeCodeUnavailable",
    "make_claude_code_adapter",
]


_log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ClaudeCodeUnavailable(RuntimeError):
    """Raised when the ``claude`` CLI cannot be found."""


@dataclass(frozen=True)
class ClaudeCodeSettings:
    cli: str = "claude"
    working_dir: str = "."
    cancel_grace_s: float = 3.0
    extra_args: tuple[str, ...] = ()
    queue_maxsize: int = 256
    env_overrides: dict[str, str] = field(default_factory=dict)


_WROTE_FILE_RE = re.compile(r"^Wrote file:?\s+(?P<path>.+)$", re.IGNORECASE)
_RAN_CMD_RE = re.compile(r"^Ran command:?\s+(?P<cmd>.+)$", re.IGNORECASE)
_ERROR_RE = re.compile(r"^Error:?\s+(?P<msg>.+)$", re.IGNORECASE)


class _ClaudeTask:
    __slots__ = (
        "artifacts",
        "cancelled",
        "exit_code",
        "handle",
        "last_note",
        "last_status",
        "process",
        "queue",
        "request",
        "task",
    )

    def __init__(self, handle: TaskHandle, request: TaskRequest, queue: asyncio.Queue) -> None:
        self.handle = handle
        self.request = request
        self.queue = queue
        self.artifacts: list[Artifact] = []
        self.cancelled: bool = False
        self.exit_code: int | None = None
        self.last_status: str = "queued"
        self.last_note: str | None = None
        self.process: asyncio.subprocess.Process | None = None
        self.task: asyncio.Task | None = None


class ClaudeCodeAdapter:
    """Wraps the ``claude`` CLI."""

    name: str = "claude_code"
    capabilities: ClassVar[set[str]] = {"code", "shell", "text"}

    def __init__(self, *, settings: ClaudeCodeSettings | None = None) -> None:
        self._settings = settings or ClaudeCodeSettings()
        self._handles: dict[str, _ClaudeTask] = {}
        self._closed: bool = False

    # ----------------------------------------------------------------- API

    async def submit(self, req: TaskRequest) -> TaskHandle:
        handle = TaskHandle(id=str(uuid.uuid4()), runtime=self.name)
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._settings.queue_maxsize)
        t = _ClaudeTask(handle=handle, request=req, queue=queue)
        self._handles[handle.id] = t
        t.task = asyncio.create_task(
            self._run(t), name=f"openmimicry.tasks.claude.{handle.id}"
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
        proc = t.process
        if proc is None:
            return
        try:
            proc.terminate()
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(proc.wait(), timeout=self._settings.cancel_grace_s)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass

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
            return TaskResult(handle=handle, status="cancelled", artifacts=t.artifacts)
        if t.last_status == "failed":
            return TaskResult(
                handle=handle,
                status="failed",
                artifacts=t.artifacts,
                error=TaskError(code="exit", message=t.last_note or "non-zero exit"),
            )
        return TaskResult(handle=handle, status="succeeded", artifacts=t.artifacts)

    async def healthcheck(self) -> bool:
        if self._closed:
            return False
        try:
            self._resolve_cli()
        except ClaudeCodeUnavailable:
            return False
        return True

    # --------------------------------------------------------------- runner

    def _resolve_cli(self) -> str:
        cli = self._settings.cli
        # If the configured path is absolute / contains a slash, trust it.
        if "/" in cli or "\\" in cli:
            if not Path(cli).is_file():
                raise ClaudeCodeUnavailable(f"claude CLI not found at {cli!r}")
            return cli
        found = shutil.which(cli)
        if found is None:
            raise ClaudeCodeUnavailable(
                f"{cli!r} not on PATH; install Claude Code or set tasks.runtimes.claude_code.cli"
            )
        return found

    def _build_prompt(self, req: TaskRequest) -> str:
        parts: list[str] = [req.instructions.strip()]
        for inp in req.inputs:
            if inp.kind == "file" and Path(inp.value).is_file():
                try:
                    body = Path(inp.value).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                parts.append(f"\n\n--- {inp.value} ---\n{body}")
            elif inp.kind == "text":
                parts.append(f"\n\n{inp.value}")
        return "".join(parts)

    def _build_env(self) -> dict[str, str]:
        # Start from a minimal subset and apply overrides. PATH must be
        # present so the CLI can locate its own subcommands.
        env: dict[str, str] = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
        }
        # Forward the common Anthropic env vars without grabbing the kitchen sink.
        for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "CLAUDE_HOME"):
            if key in os.environ:
                env[key] = os.environ[key]
        env.update(self._settings.env_overrides)
        return env

    async def _run(self, t: _ClaudeTask) -> None:
        try:
            cli = self._resolve_cli()
        except ClaudeCodeUnavailable as exc:
            t.last_status = "failed"
            t.last_note = str(exc)
            await self._offer(
                t.queue,
                TaskUpdate(
                    handle=t.handle,
                    status="failed",
                    ts=_now(),
                    error=TaskError(code="cli_missing", message=str(exc)),
                ),
            )
            await self._offer(t.queue, None)
            return

        prompt = self._build_prompt(t.request)
        argv = [cli, *self._settings.extra_args]
        env = self._build_env()
        cwd = t.request.constraints.working_dir or self._settings.working_dir

        try:
            t.process = await asyncio.create_subprocess_exec(
                *argv,
                cwd=cwd,
                env=env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as exc:  # noqa: BLE001
            t.last_status = "failed"
            t.last_note = str(exc)
            await self._offer(
                t.queue,
                TaskUpdate(
                    handle=t.handle,
                    status="failed",
                    ts=_now(),
                    error=TaskError(code="spawn_failed", message=str(exc)),
                ),
            )
            await self._offer(t.queue, None)
            return

        t.last_status = "running"
        await self._offer(
            t.queue,
            TaskUpdate(handle=t.handle, status="running", ts=_now(), note="claude spawned"),
        )

        # Feed the prompt over stdin and close it so the CLI knows we're done.
        try:
            assert t.process.stdin is not None
            t.process.stdin.write(prompt.encode("utf-8"))
            await t.process.stdin.drain()
            t.process.stdin.close()
        except (BrokenPipeError, ConnectionResetError):
            pass

        pump = asyncio.create_task(self._pump_stdout(t))
        stderr_task = asyncio.create_task(self._drain_stderr(t))

        try:
            exit_code = await t.process.wait()
        except asyncio.CancelledError:
            t.cancelled = True
            try:
                t.process.kill()
            except ProcessLookupError:
                pass
            exit_code = -1
            raise
        finally:
            await asyncio.gather(pump, stderr_task, return_exceptions=True)

        t.exit_code = exit_code
        if t.cancelled:
            t.last_status = "cancelled"
            await self._offer(
                t.queue,
                TaskUpdate(handle=t.handle, status="cancelled", ts=_now()),
            )
        elif exit_code == 0:
            t.last_status = "succeeded"
            await self._offer(
                t.queue,
                TaskUpdate(
                    handle=t.handle,
                    status="succeeded",
                    ts=_now(),
                    artifacts=list(t.artifacts),
                ),
            )
        else:
            t.last_status = "failed"
            t.last_note = f"exit {exit_code}"
            await self._offer(
                t.queue,
                TaskUpdate(
                    handle=t.handle,
                    status="failed",
                    ts=_now(),
                    error=TaskError(code=f"exit_{exit_code}", message=t.last_note),
                ),
            )

        await self._offer(t.queue, None)

    async def _pump_stdout(self, t: _ClaudeTask) -> None:
        proc = t.process
        if proc is None or proc.stdout is None:
            return
        try:
            while True:
                raw = await proc.stdout.readline()
                if not raw:
                    return
                line = raw.decode("utf-8", errors="replace").rstrip()
                note = self._parse_note(line, t)
                await self._offer(
                    t.queue,
                    TaskUpdate(
                        handle=t.handle,
                        status="running",
                        ts=_now(),
                        stdout=line,
                        note=note,
                    ),
                )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            return

    async def _drain_stderr(self, t: _ClaudeTask) -> None:
        proc = t.process
        if proc is None or proc.stderr is None:
            return
        try:
            while True:
                raw = await proc.stderr.readline()
                if not raw:
                    return
                line = raw.decode("utf-8", errors="replace").rstrip()
                await self._offer(
                    t.queue,
                    TaskUpdate(
                        handle=t.handle,
                        status="running",
                        ts=_now(),
                        note=line,
                    ),
                )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            return

    def _parse_note(self, line: str, t: _ClaudeTask) -> str | None:
        if (m := _WROTE_FILE_RE.match(line)):
            path = m.group("path").strip()
            t.artifacts.append(
                Artifact(name=Path(path).name, mime="text/plain", path=path)
            )
            return f"wrote {path}"
        if (m := _RAN_CMD_RE.match(line)):
            return f"ran {m.group('cmd').strip()}"
        if (m := _ERROR_RE.match(line)):
            return f"error: {m.group('msg').strip()}"
        return None

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
                _log.warning("ClaudeCodeAdapter: update queue full; dropping update")


def make_claude_code_adapter(*_args: Any, **_kwargs: Any) -> ClaudeCodeAdapter:
    """Factory used by the contract conftest."""
    return ClaudeCodeAdapter()
