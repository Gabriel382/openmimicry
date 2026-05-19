"""``LocalShellAdapter`` — allowlisted subprocess execution.

This is the dangerous adapter. Invariants (from the M5 brief):

* Allowlist-or-reject. Never substring-match. Match the exact command
  name AND every flag against the configured regex patterns.
* :func:`shlex.split` only. Never ``shell=True``.
* Every command goes in the audit log (path from ``audit_log`` setting).
* Cancel via ``proc.terminate()`` (SIGTERM), then ``proc.kill()`` after
  ``cancel_grace_s`` if it hasn't exited.
* Path traversal in inputs is rejected. ``working_dir`` is resolved and
  the resulting absolute path is checked against the configured root.

Streaming back-pressure follows the same drop-with-warning policy as
``EventBus``: bounded queue, oldest dropped on overflow.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shlex
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
    "AllowlistEntry",
    "LocalShellAdapter",
    "LocalShellSettings",
    "ShellNotAllowed",
    "make_local_shell_adapter",
]


_log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ShellNotAllowed(RuntimeError):
    """Raised when a command fails the allowlist."""


@dataclass(frozen=True)
class AllowlistEntry:
    """One allowlist row.

    ``cmd`` matches the exact program name (no path component allowed).
    ``flag_patterns`` is a list of regex patterns; every flag in the
    invocation must match *at least one* pattern, or the command is
    rejected. ``positional_pattern`` (optional) constrains positional
    arguments. ``max_args`` caps total argument count to defuse argv
    bombs.
    """

    cmd: str
    flag_patterns: tuple[str, ...] = ()
    positional_pattern: str | None = None
    max_args: int = 32


@dataclass(frozen=True)
class LocalShellSettings:
    allowlist: tuple[AllowlistEntry, ...] = ()
    working_dir: str = "."
    audit_log: str | None = None
    cancel_grace_s: float = 3.0
    queue_maxsize: int = 256
    extra: dict[str, Any] = field(default_factory=dict)


class _ShellTask:
    __slots__ = (
        "argv",
        "audit_logged",
        "cancelled",
        "exit_code",
        "handle",
        "last_note",
        "last_status",
        "process",
        "queue",
        "request",
        "stderr_buf",
        "task",
    )

    def __init__(self, handle: TaskHandle, request: TaskRequest, queue: asyncio.Queue) -> None:
        self.handle = handle
        self.request = request
        self.queue = queue
        self.argv: list[str] = []
        self.audit_logged: bool = False
        self.cancelled: bool = False
        self.exit_code: int | None = None
        self.last_status: str = "queued"
        self.last_note: str | None = None
        self.process: asyncio.subprocess.Process | None = None
        self.stderr_buf: list[str] = []
        self.task: asyncio.Task | None = None


class LocalShellAdapter:
    """Allowlisted local shell adapter."""

    name: str = "local_shell"
    capabilities: ClassVar[set[str]] = {"shell"}

    def __init__(self, *, settings: LocalShellSettings | None = None) -> None:
        self._settings = settings or LocalShellSettings()
        self._handles: dict[str, _ShellTask] = {}
        self._closed: bool = False

    # ----------------------------------------------------------------- API

    async def submit(self, req: TaskRequest) -> TaskHandle:
        handle = TaskHandle(id=str(uuid.uuid4()), runtime=self.name)
        try:
            argv = self._validate_command(req)
        except ShellNotAllowed as exc:
            # Build a handle anyway so the caller can stream the failure.
            t = _ShellTask(
                handle=handle,
                request=req,
                queue=asyncio.Queue(maxsize=self._settings.queue_maxsize),
            )
            self._handles[handle.id] = t
            t.last_status = "failed"
            t.last_note = str(exc)
            t.queue.put_nowait(
                TaskUpdate(
                    handle=handle,
                    status="failed",
                    ts=_now(),
                    error=TaskError(code="not_allowed", message=str(exc)),
                )
            )
            t.queue.put_nowait(None)
            self._audit(handle, argv=[], exit_code=-1, reason=f"REJECTED: {exc}")
            return handle

        queue: asyncio.Queue = asyncio.Queue(maxsize=self._settings.queue_maxsize)
        task = _ShellTask(handle=handle, request=req, queue=queue)
        task.argv = argv
        self._handles[handle.id] = task
        task.task = asyncio.create_task(self._run(task), name=f"openmimicry.tasks.shell.{handle.id}")
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
            # Hasn't started yet; the run loop will check ``cancelled``.
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
            return TaskResult(handle=handle, status="cancelled")
        if t.last_status == "failed":
            return TaskResult(
                handle=handle,
                status="failed",
                error=TaskError(code="exit", message=t.last_note or "non-zero exit"),
            )
        return TaskResult(handle=handle, status="succeeded")

    async def healthcheck(self) -> bool:
        return not self._closed

    # --------------------------------------------------------------- runner

    async def _run(self, t: _ShellTask) -> None:
        cwd = self._resolve_working_dir(t.request.constraints.working_dir)

        try:
            t.process = await asyncio.create_subprocess_exec(
                *t.argv,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as exc:  # noqa: BLE001
            t.last_status = "failed"
            t.last_note = str(exc)
            self._audit(t.handle, argv=t.argv, exit_code=-1, reason=f"SPAWN FAILED: {exc}")
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
            TaskUpdate(handle=t.handle, status="running", ts=_now(), note=" ".join(t.argv)),
        )

        stdout_task = asyncio.create_task(self._pump_stream(t.process.stdout, t, kind="stdout"))
        stderr_task = asyncio.create_task(self._pump_stream(t.process.stderr, t, kind="stderr"))

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
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)

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
                TaskUpdate(handle=t.handle, status="succeeded", ts=_now()),
            )
        else:
            t.last_status = "failed"
            stderr_tail = "".join(t.stderr_buf[-10:]).strip()
            t.last_note = f"exit {exit_code}: {stderr_tail}"[:256]
            await self._offer(
                t.queue,
                TaskUpdate(
                    handle=t.handle,
                    status="failed",
                    ts=_now(),
                    error=TaskError(code=f"exit_{exit_code}", message=t.last_note),
                ),
            )

        self._audit(t.handle, argv=t.argv, exit_code=exit_code, reason=t.last_status)
        await self._offer(t.queue, None)

    async def _pump_stream(
        self,
        reader: asyncio.StreamReader | None,
        t: _ShellTask,
        *,
        kind: str,
    ) -> None:
        if reader is None:
            return
        try:
            while True:
                raw = await reader.readline()
                if not raw:
                    return
                line = raw.decode("utf-8", errors="replace").rstrip()
                if kind == "stderr":
                    t.stderr_buf.append(line + "\n")
                await self._offer(
                    t.queue,
                    TaskUpdate(
                        handle=t.handle,
                        status="running",
                        ts=_now(),
                        stdout=line if kind == "stdout" else None,
                        note=line if kind == "stderr" else None,
                    ),
                )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — stream may close abruptly
            return

    # ----------------------------------------------------------- validation

    def _validate_command(self, req: TaskRequest) -> list[str]:
        argv = shlex.split(req.instructions)
        if not argv:
            raise ShellNotAllowed("empty command")
        if len(argv) > 64:
            raise ShellNotAllowed("argv too large")
        # Reject explicit path components in argv[0]; allowlist matches names only.
        cmd = argv[0]
        if "/" in cmd or "\\" in cmd or cmd.startswith("."):
            raise ShellNotAllowed(f"absolute / relative command paths not allowed: {cmd!r}")

        entry = next((e for e in self._settings.allowlist if e.cmd == cmd), None)
        if entry is None:
            raise ShellNotAllowed(f"command not in allowlist: {cmd!r}")
        if len(argv) - 1 > entry.max_args:
            raise ShellNotAllowed(f"too many args ({len(argv) - 1} > {entry.max_args})")

        flag_regexes = [re.compile(p) for p in entry.flag_patterns]
        positional_regex = (
            re.compile(entry.positional_pattern) if entry.positional_pattern else None
        )

        for arg in argv[1:]:
            if arg.startswith("-"):
                if not flag_regexes or not any(rx.fullmatch(arg) for rx in flag_regexes):
                    raise ShellNotAllowed(f"flag not allowed: {arg!r}")
            elif positional_regex is not None and not positional_regex.fullmatch(arg):
                raise ShellNotAllowed(f"positional arg not allowed: {arg!r}")
            # Defuse common shell-injection footguns even though we don't use shell=True.
            if any(c in arg for c in ("\n", "\r")):
                raise ShellNotAllowed(f"newline in argument: {arg!r}")

        return argv

    def _resolve_working_dir(self, candidate: str | None) -> str:
        root = Path(self._settings.working_dir).expanduser().resolve()
        if candidate is None:
            return str(root)
        # Reject path traversal: candidate must resolve inside root OR equal it.
        target = (root / candidate).resolve() if not Path(candidate).is_absolute() else Path(candidate).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ShellNotAllowed(
                f"working_dir {target} escapes configured root {root}"
            ) from exc
        return str(target)

    # ----------------------------------------------------------------- audit

    def _audit(
        self, handle: TaskHandle, *, argv: list[str], exit_code: int, reason: str
    ) -> None:
        if not self._settings.audit_log:
            return
        path = Path(self._settings.audit_log).expanduser()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(
                    f"{_now().isoformat()}\t{handle.id}\t"
                    f"exit={exit_code}\treason={reason}\t"
                    f"argv={argv!r}\n"
                )
        except OSError as exc:  # noqa: BLE001
            _log.warning("LocalShellAdapter: audit log write failed: %s", exc)

    # ------------------------------------------------------------- back-pressure

    async def _offer(self, queue: asyncio.Queue, item: Any) -> None:
        """Bounded put that drops the oldest on overflow (mirrors EventBus)."""
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
                _log.warning(
                    "LocalShellAdapter: update queue full; dropping update for handle"
                )


def make_local_shell_adapter(*_args: Any, **_kwargs: Any) -> LocalShellAdapter:
    """Entry-point factory used by the contract conftest.

    Returns an adapter with an empty allowlist — every command will be
    rejected. Production wiring (M6) constructs the adapter with the
    settings from ``AppConfig.tasks.runtimes.local_shell``.
    """
    return LocalShellAdapter()
