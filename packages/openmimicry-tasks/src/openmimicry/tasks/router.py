"""``TaskRouter`` — capability-based routing across registered adapters.

Itself a :class:`TaskRuntimeAdapter` so it composes transparently with
M6's wiring. Selection algorithm (per ``docs/task_delegation.md`` §2):

1. If ``req.preferred_runtime`` is set and that adapter is registered,
   choose it.
2. Otherwise, pick the first registered adapter whose ``capabilities``
   is a superset of ``req.capabilities_required``.
3. Otherwise, fall back to the configured ``default_runtime``.
4. Otherwise raise :class:`NoAdapterForCapabilities`.

``cancel(handle)`` / ``status(handle)`` / ``updates(handle)`` /
``result(handle)`` dispatch based on the ``handle.runtime`` field that
the chosen adapter assigned at submit time. The router remembers each
handle → adapter mapping for the lifetime of the task.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import ClassVar

from openmimicry.core.contracts import TaskRuntimeAdapter
from openmimicry.core.schemas.tasks import (
    TaskHandle,
    TaskRequest,
    TaskResult,
    TaskStatus,
    TaskUpdate,
)

from .errors import NoAdapterForCapabilities, TaskRoutingError

__all__ = ["TaskRouter"]


_log = logging.getLogger(__name__)


class TaskRouter:
    """Composes one or more :class:`TaskRuntimeAdapter` instances."""

    name: str = "router"
    capabilities: ClassVar[set[str]] = set()

    def __init__(
        self,
        *,
        adapters: dict[str, TaskRuntimeAdapter],
        default_runtime: str | None = None,
    ) -> None:
        if not adapters:
            raise TaskRoutingError("TaskRouter requires at least one adapter")
        self._adapters: dict[str, TaskRuntimeAdapter] = dict(adapters)
        if default_runtime is not None and default_runtime not in self._adapters:
            raise TaskRoutingError(
                f"default_runtime {default_runtime!r} is not in adapters ({list(self._adapters)})"
            )
        self._default_runtime = default_runtime
        self._handle_to_runtime: dict[str, str] = {}
        # Union of every adapter's capabilities — useful for /health.
        self.capabilities = set().union(*(a.capabilities for a in self._adapters.values()))

    # ----------------------------------------------------------------- API

    def select(self, req: TaskRequest) -> TaskRuntimeAdapter:
        """Pure selection function; exposed for tests and for /health probes."""
        # 1. Preferred runtime wins if registered.
        if req.preferred_runtime and req.preferred_runtime in self._adapters:
            return self._adapters[req.preferred_runtime]
        if req.preferred_runtime and req.preferred_runtime not in self._adapters:
            _log.info(
                "TaskRouter: preferred_runtime %r not registered; falling through",
                req.preferred_runtime,
            )

        # 2. Capability superset.
        required = req.capabilities_required or set()
        if required:
            for adapter in self._adapters.values():
                if required.issubset(adapter.capabilities):
                    return adapter

        # 3. Default fallback.
        if self._default_runtime is not None:
            return self._adapters[self._default_runtime]

        # 4. No match.
        raise NoAdapterForCapabilities(
            f"no adapter satisfies capabilities {required!r} (registered: {list(self._adapters)})"
        )

    async def submit(self, req: TaskRequest) -> TaskHandle:
        """Submit a task to the selected adapter and remember ownership."""
        requested_runtime = req.preferred_runtime
        runtime = requested_runtime or self._default_runtime

        # In production, a preferred runtime may be unavailable depending on the
        # installed profile. In tests/dev, intents can request "claude_code" or
        # "mcp_agent" while only a mock/default adapter is registered.
        if runtime not in self._adapters:
            runtime = self._default_runtime

        if runtime is None:
            raise TaskRoutingError("no runtime selected and no default runtime configured")

        adapter = self._adapters.get(runtime)
        if adapter is None:
            raise TaskRoutingError(f"unknown runtime {runtime!r}")

        handle = await adapter.submit(req)

        # Store the router-owned adapter key, not handle.runtime.
        self._handle_to_runtime[handle.id] = runtime

        return handle

    async def status(self, handle: TaskHandle) -> TaskStatus:
        return await self._resolve(handle).status(handle)

    async def cancel(self, handle: TaskHandle) -> None:
        adapter = self._resolve(handle)
        await adapter.cancel(handle)

    def updates(self, handle: TaskHandle) -> AsyncIterator[TaskUpdate]:
        return self._resolve(handle).updates(handle)

    async def result(self, handle: TaskHandle) -> TaskResult:
        return await self._resolve(handle).result(handle)

    async def healthcheck(self) -> bool:
        """At least one downstream adapter must be healthy."""
        for adapter in self._adapters.values():
            try:
                if await adapter.healthcheck():
                    return True
            except Exception:
                continue
        return False

    # ----------------------------------------------------------------- util

    def _resolve(self, handle: TaskHandle) -> TaskRuntimeAdapter:
        """Find the adapter that owns ``handle``."""
        runtime = self._handle_to_runtime.get(handle.id) or handle.runtime

        if runtime is None:
            raise TaskRoutingError(f"handle {handle.id!r} has no associated runtime")

        adapter = self._adapters.get(runtime)
        if adapter is None:
            raise TaskRoutingError(f"handle {handle.id!r} references unknown runtime {runtime!r}")

        return adapter

    @property
    def adapters(self) -> dict[str, TaskRuntimeAdapter]:
        """Read-only view of the registered adapters."""
        return dict(self._adapters)
