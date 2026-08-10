"""Durable task, project, event, and notification journal.

The journal is deliberately provider-neutral.  It wraps any
``TaskRuntimeAdapter`` and stores only contract-shaped data in SQLite, so a
Claude CLI task, PicoClaw task, MCP task, or future provider has the same
restart-safe history.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import sqlite3
import threading
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, cast

from openmimicry.core.contracts import TaskRuntimeAdapter
from openmimicry.core.schemas.tasks import (
    TaskError,
    TaskHandle,
    TaskRequest,
    TaskResult,
    TaskStatus,
    TaskUpdate,
)

__all__ = ["JournaledTaskRuntime", "TaskJournal"]

_log = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


class TaskJournal:
    """Small synchronous SQLite repository guarded for multi-threaded use."""

    def __init__(self, path: str) -> None:
        self.path = Path(path).expanduser()
        self._lock = threading.RLock()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(self.path, check_same_thread=False)
        except (OSError, sqlite3.Error) as exc:
            # Read-only containers and contract tests still get the same
            # semantics for this process; normal desktop installs persist.
            _log.warning(
                "Task journal could not open %s; using process memory only: %s",
                self.path,
                exc,
            )
            self.path = Path(":memory:")
            self._db = sqlite3.connect(":memory:", check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    root_path TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    provider_runtime TEXT,
                    provider_session_id TEXT,
                    repository_fingerprint TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    runtime TEXT NOT NULL,
                    project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
                    summary TEXT NOT NULL,
                    instructions TEXT NOT NULL,
                    status TEXT NOT NULL,
                    note TEXT,
                    progress REAL,
                    request_json TEXT NOT NULL,
                    result_json TEXT,
                    provider_session_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    event_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
                    level TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    read_at TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_updated ON tasks(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_events_task ON task_events(task_id, id);
                CREATE INDEX IF NOT EXISTS idx_notifications_created
                    ON notifications(created_at DESC);
                """
            )
            self._ensure_column("projects", "provider_session_id", "TEXT")
            self._ensure_column("projects", "repository_fingerprint", "TEXT")
            # A process restart cannot leave a task looking live forever.
            self._db.execute(
                """
                UPDATE tasks
                SET status='interrupted',
                    note='Backend restarted before the task reported a terminal result',
                    updated_at=?
                WHERE status IN ('queued', 'running', 'waiting_for_user')
                """,
                (_utc_now(),),
            )
            self._db.commit()
        _log.info("Task journal ready: path=%s", self.path)

    def _ensure_column(self, table: str, column: str, declaration: str) -> None:
        columns = {
            str(row["name"]) for row in self._db.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            self._db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def create_project(
        self,
        *,
        name: str,
        root_path: str,
        description: str = "",
        provider_runtime: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        identifier = project_id or str(uuid.uuid4())
        now = _utc_now()
        with self._lock:
            self._db.execute(
                """
                INSERT INTO projects
                    (id, name, root_path, description, provider_runtime, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    name.strip(),
                    str(Path(root_path).expanduser().resolve()),
                    description.strip(),
                    provider_runtime,
                    now,
                    now,
                ),
            )
            self._db.commit()
        return self.get_project(identifier)

    def list_projects(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
        return [dict(row) for row in rows]

    def get_project(self, project_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            raise KeyError(project_id)
        return dict(row)

    def project_context(self, project_id: str) -> dict[str, Any]:
        """Return project metadata plus a cheap repository-change fingerprint."""

        project = self.get_project(project_id)
        fingerprint = self.repository_fingerprint(str(project["root_path"]))
        unchanged = fingerprint == project.get("repository_fingerprint")
        return {
            **project,
            "current_fingerprint": fingerprint,
            "resume_session_id": project.get("provider_session_id") if unchanged else None,
            "repository_changed": not unchanged,
        }

    @staticmethod
    def repository_fingerprint(root_path: str) -> str:
        """Fingerprint Git metadata without reading the entire repository."""

        root = Path(root_path).expanduser().resolve()
        digest = hashlib.sha256(str(root).encode())
        git = root / ".git"
        candidates = [git / "HEAD", git / "index"]
        head = git / "HEAD"
        try:
            if head.is_file():
                value = head.read_text(encoding="utf-8", errors="replace").strip()
                digest.update(value.encode())
                if value.startswith("ref: "):
                    candidates.append(git / value[5:].strip())
            for candidate in candidates:
                if candidate.is_file():
                    stats = candidate.stat()
                    digest.update(str(candidate.relative_to(root)).encode())
                    digest.update(f"{stats.st_mtime_ns}:{stats.st_size}".encode())
        except OSError:
            pass
        return digest.hexdigest()

    def record_submission(self, handle: TaskHandle, request: TaskRequest) -> None:
        now = _utc_now()
        project_id = request.metadata.get("project_id")
        with self._lock:
            self._db.execute(
                """
                INSERT OR REPLACE INTO tasks
                    (id, runtime, project_id, summary, instructions, status,
                     request_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'queued', ?, ?, ?)
                """,
                (
                    handle.id,
                    handle.runtime,
                    project_id if isinstance(project_id, str) else None,
                    request.summary,
                    request.instructions,
                    _json(request.model_dump(mode="json")),
                    now,
                    now,
                ),
            )
            fingerprint = request.metadata.get("repository_fingerprint")
            if isinstance(project_id, str) and isinstance(fingerprint, str):
                self._db.execute(
                    "UPDATE projects SET repository_fingerprint=?, updated_at=? WHERE id=?",
                    (fingerprint, now, project_id),
                )
            self._db.commit()
        _log.info(
            "Task %s persisted: runtime=%s summary=%s",
            handle.id,
            handle.runtime,
            request.summary,
        )

    def record_update(self, update: TaskUpdate) -> None:
        now = _utc_now()
        provider_session = update.metadata.get("session_id")
        note = update.note or (update.error.message if update.error is not None else None)
        with self._lock:
            self._db.execute(
                """
                UPDATE tasks
                SET status=?, note=COALESCE(?, note), progress=?,
                    provider_session_id=COALESCE(?, provider_session_id),
                    updated_at=?
                WHERE id=?
                """,
                (
                    update.status,
                    note,
                    update.progress,
                    provider_session if isinstance(provider_session, str) else None,
                    now,
                    update.handle.id,
                ),
            )
            self._db.execute(
                "INSERT INTO task_events (task_id, event_json, created_at) VALUES (?, ?, ?)",
                (
                    update.handle.id,
                    _json(update.model_dump(mode="json")),
                    now,
                ),
            )
            self._db.commit()
        if update.status in {"failed", "cancelled", "interrupted"}:
            _log.warning(
                "Task %s update persisted: status=%s detail=%s",
                update.handle.id,
                update.status,
                note,
            )

    def record_result(self, result: TaskResult) -> None:
        now = _utc_now()
        with self._lock:
            self._db.execute(
                """
                UPDATE tasks SET status=?, result_json=?, updated_at=? WHERE id=?
                """,
                (
                    result.status,
                    _json(result.model_dump(mode="json")),
                    now,
                    result.handle.id,
                ),
            )
            task_row = self._db.execute(
                "SELECT project_id, provider_session_id FROM tasks WHERE id=?",
                (result.handle.id,),
            ).fetchone()
            provider_session = result.metadata.get("session_id")
            if (
                result.status == "succeeded"
                and task_row is not None
                and isinstance(task_row["project_id"], str)
            ):
                session = (
                    provider_session
                    if isinstance(provider_session, str)
                    else task_row["provider_session_id"]
                )
                project_row = self._db.execute(
                    "SELECT root_path FROM projects WHERE id=?",
                    (task_row["project_id"],),
                ).fetchone()
                fingerprint = (
                    self.repository_fingerprint(str(project_row["root_path"]))
                    if project_row is not None
                    else None
                )
                if isinstance(session, str) and session:
                    self._db.execute(
                        """
                        UPDATE projects
                        SET provider_session_id=?, repository_fingerprint=COALESCE(?, repository_fingerprint),
                            updated_at=?
                        WHERE id=?
                        """,
                        (session, fingerprint, now, task_row["project_id"]),
                    )
            if result.status in {"succeeded", "failed", "cancelled", "interrupted"}:
                title = (
                    "Task completed" if result.status == "succeeded" else f"Task {result.status}"
                )
                message = result.summary or (
                    result.error.message if result.error is not None else result.handle.id
                )
                self._db.execute(
                    """
                    INSERT INTO notifications
                        (id, task_id, level, title, message, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        result.handle.id,
                        "info" if result.status == "succeeded" else "warning",
                        title,
                        message,
                        now,
                    ),
                )
            self._db.commit()
        if result.status == "succeeded":
            _log.info("Task %s result persisted: succeeded", result.handle.id)
        else:
            _log.warning(
                "Task %s result persisted: status=%s detail=%s",
                result.handle.id,
                result.status,
                result.error.message if result.error is not None else result.summary,
            )

    def list_tasks(
        self, *, limit: int = 100, project_id: str | None = None
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM tasks"
        values: tuple[Any, ...]
        if project_id:
            query += " WHERE project_id=?"
            values = (project_id, limit)
        else:
            values = (limit,)
        query += " ORDER BY updated_at DESC LIMIT ?"
        with self._lock:
            rows = self._db.execute(query, values).fetchall()
        return [dict(row) for row in rows]

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            events = self._db.execute(
                "SELECT event_json FROM task_events WHERE task_id=? ORDER BY id",
                (task_id,),
            ).fetchall()
        if row is None:
            raise KeyError(task_id)
        result = dict(row)
        result["events"] = [json.loads(event["event_json"]) for event in events]
        return result

    def list_notifications(self, *, unread_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM notifications"
        if unread_only:
            query += " WHERE read_at IS NULL"
        query += " ORDER BY created_at DESC LIMIT 200"
        with self._lock:
            rows = self._db.execute(query).fetchall()
        return [dict(row) for row in rows]

    def mark_notification_read(self, notification_id: str) -> None:
        with self._lock:
            cursor = self._db.execute(
                "UPDATE notifications SET read_at=? WHERE id=?",
                (_utc_now(), notification_id),
            )
            self._db.commit()
        if cursor.rowcount == 0:
            raise KeyError(notification_id)

    def create_notification(
        self,
        title: str,
        message: str,
        *,
        level: str = "info",
    ) -> str:
        identifier = str(uuid.uuid4())
        with self._lock:
            self._db.execute(
                """
                INSERT INTO notifications (id, task_id, level, title, message, created_at)
                VALUES (?, NULL, ?, ?, ?, ?)
                """,
                (identifier, level, title, message, _utc_now()),
            )
            self._db.commit()
        return identifier


class JournaledTaskRuntime:
    """Multiplex task updates while persisting their complete lifecycle."""

    name = "journaled"
    capabilities: ClassVar[set[str]] = set()

    def __init__(self, inner: TaskRuntimeAdapter, journal: TaskJournal) -> None:
        self._inner = inner
        self.journal = journal
        self.capabilities = set(inner.capabilities)
        self._queues: dict[str, list[asyncio.Queue[TaskUpdate | None]]] = {}
        self._monitors: dict[str, asyncio.Task[None]] = {}
        self._results: dict[str, TaskResult] = {}
        self._history: dict[str, list[TaskUpdate]] = {}

    async def submit(self, req: TaskRequest) -> TaskHandle:
        handle = await self._inner.submit(req)
        self.journal.record_submission(handle, req)
        self._history[handle.id] = []
        self._monitors[handle.id] = asyncio.create_task(
            self._monitor(handle), name=f"openmimicry.task-journal.{handle.id}"
        )
        return handle

    async def _monitor(self, handle: TaskHandle) -> None:
        try:
            async for update in self._inner.updates(handle):
                self._history.setdefault(handle.id, []).append(update)
                self.journal.record_update(update)
                for queue in tuple(self._queues.get(handle.id, ())):
                    await queue.put(update)
            result = await self._inner.result(handle)
        except asyncio.CancelledError:
            result = TaskResult(handle=handle, status="interrupted")
            raise
        except Exception as exc:
            _log.exception("Task %s monitor failed", handle.id)
            result = TaskResult(
                handle=handle,
                status="failed",
                error=TaskError(code="adapter_monitor_failed", message=str(exc)),
            )
        finally:
            if "result" in locals():
                self._results[handle.id] = result
                self.journal.record_result(result)
            for queue in tuple(self._queues.get(handle.id, ())):
                await queue.put(None)

    async def status(self, handle: TaskHandle) -> TaskStatus:
        return await self._inner.status(handle)

    async def cancel(self, handle: TaskHandle) -> None:
        await self._inner.cancel(handle)

    def updates(self, handle: TaskHandle) -> AsyncIterator[TaskUpdate]:
        return self._updates(handle)

    async def _updates(self, handle: TaskHandle) -> AsyncIterator[TaskUpdate]:
        queue: asyncio.Queue[TaskUpdate | None] = asyncio.Queue()
        self._queues.setdefault(handle.id, []).append(queue)
        try:
            # A CLI can fail before the websocket/dashboard subscribes. Replay
            # every already-observed update so a fast failure is never silent.
            for update in tuple(self._history.get(handle.id, ())):
                yield update
            monitor = self._monitors.get(handle.id)
            if monitor is not None and monitor.done():
                return
            while True:
                item = await queue.get()
                if item is None:
                    return
                yield item
        finally:
            with contextlib.suppress(ValueError):
                self._queues.get(handle.id, []).remove(queue)

    async def result(self, handle: TaskHandle) -> TaskResult:
        monitor = self._monitors.get(handle.id)
        if monitor is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await monitor
        return self._results.get(
            handle.id,
            TaskResult(
                handle=handle,
                status="failed",
                error=TaskError(code="unknown_handle", message="Task result is unavailable"),
            ),
        )

    async def healthcheck(self) -> bool:
        return await self._inner.healthcheck()

    async def diagnostics(self) -> dict[str, Any]:
        probe = getattr(self._inner, "diagnostics", None)
        if callable(probe):
            diagnostics = cast(Callable[[], Awaitable[dict[str, Any]]], probe)
            runtimes = await diagnostics()
        else:
            runtimes = {}
        return {
            "journal_path": str(self.journal.path),
            "persistent": self.journal.path != Path(":memory:"),
            "runtimes": runtimes,
        }

    def adapter(self, name: str) -> Any | None:
        """Return a named underlying adapter for local configuration routes."""

        adapters = getattr(self._inner, "adapters", {})
        return adapters.get(name) if isinstance(adapters, dict) else None

    async def close(self) -> None:
        for monitor in self._monitors.values():
            if not monitor.done():
                monitor.cancel()
        if self._monitors:
            await asyncio.gather(*self._monitors.values(), return_exceptions=True)
        closer = getattr(self._inner, "close", None)
        if callable(closer):
            await cast(Callable[[], Awaitable[Any]], closer)()
        self.journal.close()
