"""Task runtime adapter Protocol.

Source of truth: ``docs/contracts.md`` §6.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from ..schemas.tasks import (
    TaskHandle,
    TaskRequest,
    TaskResult,
    TaskStatus,
    TaskUpdate,
)

__all__ = ["TaskRuntimeAdapter"]


@runtime_checkable
class TaskRuntimeAdapter(Protocol):
    """A backend that can execute a ``TaskRequest`` (mcp-agent, Claude Code,
    local shell, …).

    Implementations live in ``openmimicry-tasks`` under ``adapters/``.
    """

    name: str
    capabilities: set[str]

    async def submit(self, req: TaskRequest) -> TaskHandle: ...
    async def status(self, handle: TaskHandle) -> TaskStatus: ...
    async def cancel(self, handle: TaskHandle) -> None: ...

    def updates(self, handle: TaskHandle) -> AsyncIterator[TaskUpdate]:
        """Stream of ``TaskUpdate``s until the task reaches a terminal state."""
        ...

    async def result(self, handle: TaskHandle) -> TaskResult: ...
    async def healthcheck(self) -> bool: ...
