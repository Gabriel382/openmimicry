"""Persistent projects, task history, and non-disruptive notifications."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

from fastapi import APIRouter, HTTPException, Query, Request
from openmimicry.core.schemas.tasks import TaskConstraints, TaskRequest
from pydantic import BaseModel, Field

from ..user_settings import persist_task_runtime_settings

__all__ = ["router"]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    root_path: str = Field(min_length=1, max_length=4096)
    description: str = Field(default="", max_length=4000)
    provider_runtime: str | None = Field(default=None, max_length=64)


class TaskCreate(BaseModel):
    summary: str = Field(min_length=1, max_length=256)
    instructions: str = Field(min_length=1, max_length=100_000)
    project_id: str | None = None
    preferred_runtime: str | None = None
    capabilities: set[str] = set()


class ClaudeSettingsUpdate(BaseModel):
    cli: str = Field(default="claude", min_length=1, max_length=4096)
    working_dir: str = Field(default=".", min_length=1, max_length=4096)
    auth_mode: str = Field(default="subscription", pattern="^(subscription|api)$")
    permission_mode: str = Field(default="acceptEdits", min_length=1, max_length=64)
    model: str | None = Field(default=None, max_length=128)
    max_turns: int | None = Field(default=None, ge=1, le=1000)


router = APIRouter(prefix="/tasks", tags=["tasks"])


def _runtime(request: Request):
    runtime = request.app.state.wiring.tasks
    if not hasattr(runtime, "journal"):
        raise HTTPException(status_code=409, detail="persistent task journal is unavailable")
    return runtime


@router.get("")
async def list_tasks(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    project_id: str | None = None,
) -> dict[str, object]:
    runtime = _runtime(request)
    return {"tasks": runtime.journal.list_tasks(limit=limit, project_id=project_id)}


@router.post("", status_code=202)
async def submit_task(values: TaskCreate, request: Request) -> dict[str, object]:
    runtime = _runtime(request)
    working_dir: str | None = None
    preferred_runtime = values.preferred_runtime
    if values.project_id:
        try:
            project = runtime.journal.project_context(values.project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="unknown project") from exc
        working_dir = project["root_path"]
        if preferred_runtime is None and isinstance(project.get("provider_runtime"), str):
            preferred_runtime = project["provider_runtime"]
    metadata: dict[str, object] = {}
    if values.project_id:
        metadata = {
            "project_id": values.project_id,
            "repository_fingerprint": project["current_fingerprint"],
        }
        if isinstance(project.get("resume_session_id"), str):
            metadata["provider_session_id"] = project["resume_session_id"]
    handle = await runtime.submit(
        TaskRequest(
            summary=values.summary,
            instructions=values.instructions,
            capabilities_required=values.capabilities,
            preferred_runtime=preferred_runtime,
            constraints=TaskConstraints(working_dir=working_dir),
            metadata=metadata,
        )
    )
    return {"handle": handle.model_dump(mode="json")}


@router.get("/projects")
async def list_projects(request: Request) -> dict[str, object]:
    return {"projects": _runtime(request).journal.list_projects()}


@router.post("/projects", status_code=201)
async def create_project(values: ProjectCreate, request: Request) -> dict[str, object]:
    try:
        project = _runtime(request).journal.create_project(**values.model_dump())
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"project": project}


@router.get("/notifications")
async def list_notifications(request: Request, unread_only: bool = False) -> dict[str, object]:
    items = _runtime(request).journal.list_notifications(unread_only=unread_only)
    return {"notifications": items, "unread": sum(item["read_at"] is None for item in items)}


@router.get("/runtime-status")
async def runtime_status(request: Request) -> dict[str, object]:
    """Probe task adapters without submitting a paid/model-backed request."""

    runtime = _runtime(request)
    probe = getattr(runtime, "diagnostics", None)
    if not callable(probe):
        return {
            "journal_path": None,
            "persistent": False,
            "runtimes": {},
            "error": "task runtime does not expose diagnostics",
        }
    diagnostics = cast(Callable[[], Awaitable[dict[str, object]]], probe)
    return await diagnostics()


def _claude_adapter(request: Request):
    adapter = _runtime(request).adapter("claude_code")
    if adapter is None:
        raise HTTPException(status_code=409, detail="Claude Code runtime is not configured")
    return adapter


@router.get("/settings/claude")
async def get_claude_settings(request: Request) -> dict[str, object]:
    adapter = _claude_adapter(request)
    values = adapter._settings
    return {
        "cli": values.cli,
        "working_dir": values.working_dir,
        "auth_mode": values.auth_mode,
        "permission_mode": values.permission_mode,
        "model": values.model,
        "max_turns": values.max_turns,
    }


@router.post("/settings/claude")
async def update_claude_settings(
    values: ClaudeSettingsUpdate, request: Request
) -> dict[str, object]:
    from dataclasses import replace

    adapter = _claude_adapter(request)
    path = Path(values.working_dir).expanduser()
    if not path.is_dir():
        raise HTTPException(status_code=422, detail="Claude working directory does not exist")
    settings = replace(adapter._settings, **values.model_dump())
    adapter.reconfigure(settings)
    persist_task_runtime_settings("claude_code", values.model_dump(exclude_none=True))
    return {"ok": True, "settings": values.model_dump(mode="json")}


@router.post("/notifications/{notification_id}/read")
async def read_notification(notification_id: str, request: Request) -> dict[str, bool]:
    try:
        _runtime(request).journal.mark_notification_read(notification_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="unknown notification") from exc
    return {"ok": True}


@router.get("/{task_id}")
async def get_task(task_id: str, request: Request) -> dict[str, object]:
    try:
        return {"task": _runtime(request).journal.get_task(task_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="unknown task") from exc
