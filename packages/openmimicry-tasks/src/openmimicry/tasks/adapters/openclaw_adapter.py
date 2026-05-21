"""``OpenClawAdapter`` — stub. Concrete implementation is post-v0.2.

See ``docs/modules/post_v0_2_modalities.md``. The stub satisfies the
``TaskRuntimeAdapter`` Protocol's shape but every method raises so
accidental wiring is loud.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, ClassVar

from openmimicry.core.schemas.tasks import (
    TaskHandle,
    TaskRequest,
    TaskResult,
    TaskStatus,
    TaskUpdate,
)

__all__ = ["OpenClawAdapter"]


_MSG = "OpenClawAdapter is a post-v0.2 stub; see docs/modules/post_v0_2_modalities.md."


class OpenClawAdapter:
    """Placeholder. Raises on every call."""

    name: str = "openclaw"
    capabilities: ClassVar[set[str]] = set()

    def __init__(self, **_kwargs: Any) -> None:
        return None

    async def submit(self, req: TaskRequest) -> TaskHandle:
        raise NotImplementedError(_MSG)

    async def status(self, handle: TaskHandle) -> TaskStatus:
        raise NotImplementedError(_MSG)

    async def cancel(self, handle: TaskHandle) -> None:
        raise NotImplementedError(_MSG)

    def updates(self, handle: TaskHandle) -> AsyncIterator[TaskUpdate]:
        raise NotImplementedError(_MSG)

    async def result(self, handle: TaskHandle) -> TaskResult:
        raise NotImplementedError(_MSG)

    async def healthcheck(self) -> bool:
        return False
