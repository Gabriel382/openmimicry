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
import contextlib
import json
import logging
import os
import re
import shutil
import subprocess
import uuid
from collections import deque
from collections.abc import AsyncIterator, Sequence
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
    auth_mode: str = "subscription"
    output_format: str = "stream-json"
    permission_mode: str = "acceptEdits"
    max_turns: int | None = None
    resume_sessions: bool = True
    cancel_grace_s: float = 3.0
    diagnostic_timeout_s: float = 8.0
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
        "failure",
        "handle",
        "last_note",
        "last_status",
        "process",
        "queue",
        "request",
        "session_id",
        "stderr_tail",
        "summary",
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
        self.session_id: str | None = None
        self.failure: TaskError | None = None
        self.stderr_tail: deque[str] = deque(maxlen=12)
        self.summary: str | None = None


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
        t.task = asyncio.create_task(self._run(t), name=f"openmimicry.tasks.claude.{handle.id}")
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
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()

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
            with contextlib.suppress(asyncio.CancelledError):
                await t.task
        if t.cancelled:
            return TaskResult(handle=handle, status="cancelled", artifacts=t.artifacts)
        if t.last_status == "failed":
            return TaskResult(
                handle=handle,
                status="failed",
                artifacts=t.artifacts,
                error=t.failure or TaskError(code="exit", message=t.last_note or "non-zero exit"),
            )
        return TaskResult(
            handle=handle,
            status="succeeded",
            artifacts=t.artifacts,
            summary=t.summary,
            metadata={"session_id": t.session_id} if t.session_id else {},
        )

    async def healthcheck(self) -> bool:
        if self._closed:
            return False
        try:
            self._resolve_cli()
        except ClaudeCodeUnavailable:
            return False
        return Path(self._settings.working_dir).expanduser().is_dir()

    async def diagnostics(self) -> dict[str, Any]:
        """Return actionable, secret-free CLI/auth/cwd diagnostics.

        The probes do not submit a model request and therefore do not consume
        Claude usage.  They intentionally use the same curated environment,
        wrapper handling, and working directory as a real task.
        """

        cwd = Path(self._settings.working_dir).expanduser()
        result: dict[str, Any] = {
            "adapter": self.name,
            "configured_cli": self._settings.cli,
            "working_dir": str(cwd),
            "working_dir_exists": cwd.is_dir(),
            "auth_mode": self._settings.auth_mode,
            "permission_mode": self._settings.permission_mode,
            "available": False,
            "authenticated": False,
        }
        try:
            cli = self._resolve_cli()
        except ClaudeCodeUnavailable as exc:
            result["error"] = str(exc)
            return result
        result["resolved_cli"] = cli
        if not cwd.is_dir():
            result["error"] = (
                "Configured Claude working directory does not exist. "
                "Correct tasks.runtimes.claude_code.working_dir."
            )
            return result

        version = await self._probe(cli, ("--version",), cwd=str(cwd))
        result["version"] = version["output"]
        if version["returncode"] != 0:
            result["error"] = version["error"] or "claude --version failed"
            return result

        auth = await self._probe(cli, ("auth", "status"), cwd=str(cwd))
        result["auth_status"] = auth["output"]
        result["authenticated"] = auth["returncode"] == 0
        result["available"] = result["authenticated"]
        if not result["authenticated"]:
            result["error"] = (
                auth["error"]
                or auth["output"]
                or (
                    "Claude is not authenticated for the account that starts OpenMimicry. "
                    "Run `claude auth login`, then restart the backend."
                )
            )
        return result

    # --------------------------------------------------------------- runner

    def _resolve_cli(self) -> str:
        cli = self._settings.cli
        # If the configured path is absolute / contains a slash, trust it.
        if "/" in cli or "\\" in cli:
            if not Path(cli).is_file():
                raise ClaudeCodeUnavailable(f"claude CLI not found at {cli!r}")
            return cli
        found = shutil.which(cli)
        if found is not None:
            return found
        if os.name == "nt" and cli.casefold() in {"claude", "claude.exe"}:
            for candidate in self._windows_cli_candidates():
                if candidate.is_file():
                    return str(candidate)
        raise ClaudeCodeUnavailable(
            f"{cli!r} not on the backend PATH; restart PowerShell after installing Claude "
            "Code or set tasks.runtimes.claude_code.cli to the absolute executable path"
        )

    @staticmethod
    def _windows_cli_candidates() -> tuple[Path, ...]:
        """Known native/npm/WinGet locations used by Claude Code on Windows."""

        user = Path(os.environ.get("USERPROFILE", ""))
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        roaming = Path(os.environ.get("APPDATA", ""))
        candidates = (
            user / ".local" / "bin" / "claude.exe",
            local / "Microsoft" / "WinGet" / "Links" / "claude.exe",
            roaming / "npm" / "claude.cmd",
        )
        return tuple(path for path in candidates if str(path.parent) not in {".", ""})

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
        env: dict[str, str] = {}
        for key in (
            "PATH",
            "HOME",
            "USERPROFILE",
            "HOMEDRIVE",
            "HOMEPATH",
            "SYSTEMROOT",
            "WINDIR",
            "SYSTEMDRIVE",
            "COMSPEC",
            "PATHEXT",
            "APPDATA",
            "LOCALAPPDATA",
            "TEMP",
            "TMP",
            "LANG",
            "LC_ALL",
            "CLAUDE_HOME",
            "CLAUDE_CONFIG_DIR",
            "CLAUDE_CODE_GIT_BASH_PATH",
            "CLAUDE_CODE_USE_POWERSHELL_TOOL",
        ):
            value = os.environ.get(key)
            if value:
                env[key] = value
        # Subscription mode deliberately leaves API credentials out so the
        # locally authenticated Claude CLI uses the user's Claude plan.
        if self._settings.auth_mode == "api":
            for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"):
                if key in os.environ:
                    env[key] = os.environ[key]
        env.update(self._settings.env_overrides)
        return env

    def _build_command(
        self,
        cli: str,
        args: Sequence[str],
        *,
        env: dict[str, str],
        windows: bool | None = None,
    ) -> tuple[str, ...]:
        """Build a direct executable command, safely wrapping Windows batch shims."""

        is_windows = os.name == "nt" if windows is None else windows
        if is_windows and Path(cli).suffix.casefold() in {".cmd", ".bat"}:
            comspec = env.get("COMSPEC") or os.environ.get("COMSPEC") or "cmd.exe"
            command_line = subprocess.list2cmdline([cli, *args])
            return (comspec, "/d", "/s", "/c", command_line)
        return (cli, *args)

    async def _probe(
        self,
        cli: str,
        args: Sequence[str],
        *,
        cwd: str,
    ) -> dict[str, Any]:
        env = self._build_env()
        argv = self._build_command(cli, args, env=env)
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                cwd=cwd,
                env=env,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self._settings.diagnostic_timeout_s,
            )
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            with contextlib.suppress(Exception):
                await process.wait()
            return {
                "returncode": -1,
                "output": "",
                "error": f"`{' '.join(args)}` timed out",
            }
        except Exception as exc:
            return {"returncode": -1, "output": "", "error": str(exc)}
        return {
            "returncode": int(process.returncode or 0),
            "output": stdout.decode("utf-8", errors="replace").strip(),
            "error": stderr.decode("utf-8", errors="replace").strip(),
        }

    async def _run(self, t: _ClaudeTask) -> None:
        try:
            cli = self._resolve_cli()
        except ClaudeCodeUnavailable as exc:
            t.last_status = "failed"
            t.last_note = str(exc)
            t.failure = TaskError(code="cli_missing", message=str(exc))
            _log.error("Claude task %s rejected: %s", t.handle.id, exc)
            await self._offer(
                t.queue,
                TaskUpdate(
                    handle=t.handle,
                    status="failed",
                    ts=_now(),
                    note=str(exc),
                    error=t.failure,
                ),
            )
            await self._offer(t.queue, None)
            return

        prompt = self._build_prompt(t.request)
        args = [
            "-p",
            "--input-format",
            "text",
            "--output-format",
            self._settings.output_format,
            "--verbose",
            "--permission-mode",
            self._settings.permission_mode,
        ]
        if self._settings.max_turns is not None:
            args.extend(["--max-turns", str(self._settings.max_turns)])
        requested_session = t.request.metadata.get("provider_session_id")
        if (
            self._settings.resume_sessions
            and isinstance(requested_session, str)
            and requested_session.strip()
        ):
            args.extend(["--resume", requested_session.strip()])
        args.extend(self._settings.extra_args)
        env = self._build_env()
        cwd = t.request.constraints.working_dir or self._settings.working_dir
        cwd_path = Path(cwd).expanduser()
        if not cwd_path.is_dir():
            message = (
                f"Claude working directory does not exist: {cwd_path}. "
                "Correct tasks.runtimes.claude_code.working_dir."
            )
            t.last_status = "failed"
            t.last_note = message
            t.failure = TaskError(code="working_directory_missing", message=message)
            _log.error("Claude task %s rejected: %s", t.handle.id, message)
            await self._offer(
                t.queue,
                TaskUpdate(
                    handle=t.handle,
                    status="failed",
                    ts=_now(),
                    note=message,
                    error=t.failure,
                ),
            )
            await self._offer(t.queue, None)
            return
        argv = self._build_command(cli, args, env=env)
        _log.info(
            "Claude task %s starting: cli=%s cwd=%s auth=%s permission=%s",
            t.handle.id,
            cli,
            cwd_path,
            self._settings.auth_mode,
            self._settings.permission_mode,
        )

        try:
            t.process = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(cwd_path),
                env=env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as exc:
            t.last_status = "failed"
            t.last_note = f"{type(exc).__name__}: {exc}"
            t.failure = TaskError(code="spawn_failed", message=t.last_note)
            _log.exception(
                "Claude task %s could not start: cli=%s cwd=%s",
                t.handle.id,
                cli,
                cwd_path,
            )
            await self._offer(
                t.queue,
                TaskUpdate(
                    handle=t.handle,
                    status="failed",
                    ts=_now(),
                    note=t.last_note,
                    error=t.failure,
                ),
            )
            await self._offer(t.queue, None)
            return

        t.last_status = "running"
        _log.info(
            "Claude task %s spawned: pid=%s",
            t.handle.id,
            getattr(t.process, "pid", "unknown"),
        )
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
            with contextlib.suppress(ProcessLookupError):
                t.process.kill()
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
        elif exit_code == 0 and t.failure is None:
            t.last_status = "succeeded"
            _log.info("Claude task %s completed successfully", t.handle.id)
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
            stderr_detail = "\n".join(t.stderr_tail).strip()
            if t.failure is None:
                t.last_note = stderr_detail or f"Claude exited with code {exit_code}"
                t.failure = TaskError(
                    code=f"exit_{exit_code}",
                    message=t.last_note,
                )
            else:
                t.last_note = t.failure.message
            _log.error(
                "Claude task %s failed: exit=%s detail=%s",
                t.handle.id,
                exit_code,
                t.last_note,
            )
            await self._offer(
                t.queue,
                TaskUpdate(
                    handle=t.handle,
                    status="failed",
                    ts=_now(),
                    note=t.last_note,
                    error=t.failure,
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
                display, note, metadata = self._parse_output(line, t)
                await self._offer(
                    t.queue,
                    TaskUpdate(
                        handle=t.handle,
                        status="running",
                        ts=_now(),
                        stdout=display,
                        note=note,
                        metadata=metadata,
                    ),
                )
        except asyncio.CancelledError:
            raise
        except Exception:
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
                if line:
                    t.stderr_tail.append(line)
                    _log.warning("Claude task %s stderr: %s", t.handle.id, line)
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
        except Exception:
            return

    def _parse_note(self, line: str, t: _ClaudeTask) -> str | None:
        if m := _WROTE_FILE_RE.match(line):
            path = m.group("path").strip()
            t.artifacts.append(Artifact(name=Path(path).name, mime="text/plain", path=path))
            return f"wrote {path}"
        if m := _RAN_CMD_RE.match(line):
            return f"ran {m.group('cmd').strip()}"
        if m := _ERROR_RE.match(line):
            return f"error: {m.group('msg').strip()}"
        return None

    def _parse_output(self, line: str, t: _ClaudeTask) -> tuple[str, str | None, dict[str, Any]]:
        """Parse Claude's stream-json while remaining compatible with plain output."""

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return line, self._parse_note(line, t), {}
        if not isinstance(event, dict):
            return line, None, {}
        metadata: dict[str, Any] = {}
        session_id = event.get("session_id")
        if isinstance(session_id, str) and session_id:
            t.session_id = session_id
            metadata["session_id"] = session_id
        event_type = str(event.get("type", "event"))
        if event_type == "result":
            result = event.get("result")
            if isinstance(result, str):
                t.summary = result
                if event.get("is_error") is True:
                    subtype = str(event.get("subtype") or "provider_error")
                    t.failure = TaskError(code=subtype, message=result)
                    t.last_note = result
                return result, "Claude completed", metadata
        message = event.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, list):
                chunks = [
                    str(item.get("text", ""))
                    for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                ]
                text = "".join(chunks)
                if text:
                    return text, None, metadata
        return line, event_type, metadata

    async def _offer(self, queue: asyncio.Queue, item: Any) -> None:
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                queue.get_nowait()
            try:
                queue.put_nowait(item)
            except asyncio.QueueFull:
                _log.warning("ClaudeCodeAdapter: update queue full; dropping update")


def make_claude_code_adapter(*_args: Any, **_kwargs: Any) -> ClaudeCodeAdapter:
    """Factory used by the contract conftest."""
    return ClaudeCodeAdapter()
