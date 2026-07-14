"""Task delegation schemas — frozen Pydantic models.

Source of truth: ``docs/contracts.md`` §6.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

__all__ = [
    "Artifact",
    "TaskConstraints",
    "TaskError",
    "TaskHandle",
    "TaskInput",
    "TaskRequest",
    "TaskResult",
    "TaskStatus",
    "TaskStatusName",
    "TaskUpdate",
]


TaskStatusName = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class TaskInput(BaseModel):
    """A single input artefact attached to a ``TaskRequest``."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["file", "url", "text", "blob"]
    value: str
    mime: str | None = None


class TaskConstraints(BaseModel):
    """Caller-side guard rails: timeouts, cost, network access, working dir."""

    model_config = ConfigDict(frozen=True)

    timeout_s: int | None = None
    max_cost_usd: float | None = None
    working_dir: str | None = None
    network: bool = True


class TaskRequest(BaseModel):
    """A request submitted to a ``TaskRuntimeAdapter``."""

    model_config = ConfigDict(frozen=True)

    summary: str
    instructions: str
    inputs: list[TaskInput] = []
    capabilities_required: set[str] = set()
    preferred_runtime: str | None = None
    constraints: TaskConstraints = TaskConstraints()
    metadata: dict[str, Any] = {}


class TaskHandle(BaseModel):
    """Stable identifier returned by ``TaskRuntimeAdapter.submit``."""

    model_config = ConfigDict(frozen=True)

    id: str
    runtime: str


class TaskError(BaseModel):
    """A structured error carried inside ``TaskUpdate`` / ``TaskResult``."""

    model_config = ConfigDict(frozen=True)

    code: str
    message: str


class Artifact(BaseModel):
    """An output artefact produced by a task.

    Exactly one of ``path`` / ``inline`` is set in practice; the runtime adapter
    is responsible for picking the right one.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    mime: str
    path: str | None = None
    inline: str | None = None


class TaskStatus(BaseModel):
    """A point-in-time status response from ``TaskRuntimeAdapter.status``."""

    model_config = ConfigDict(frozen=True)

    handle: TaskHandle
    status: TaskStatusName
    note: str | None = None
    progress: float | None = None


class TaskUpdate(BaseModel):
    """A streamed update yielded by ``TaskRuntimeAdapter.updates``."""

    model_config = ConfigDict(frozen=True)

    handle: TaskHandle
    status: TaskStatusName
    note: str | None = None
    progress: float | None = None
    stdout: str | None = None
    artifacts: list[Artifact] = []
    error: TaskError | None = None
    ts: datetime


class TaskResult(BaseModel):
    """The terminal result returned by ``TaskRuntimeAdapter.result``."""

    model_config = ConfigDict(frozen=True)

    handle: TaskHandle
    status: TaskStatusName
    artifacts: list[Artifact] = []
    summary: str | None = None
    error: TaskError | None = None
