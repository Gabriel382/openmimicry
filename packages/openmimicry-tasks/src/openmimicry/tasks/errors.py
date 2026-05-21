"""Typed errors for the task stack.

The schema-level :class:`TaskError` is the value carried inside a
``TaskUpdate`` or ``TaskResult``. The classes here are *raised* exceptions
used by the router and adapters.
"""

from __future__ import annotations

from openmimicry.core.schemas.tasks import TaskError

__all__ = [
    "NoAdapterForCapabilities",
    "TaskAdapterError",
    "TaskError",
    "TaskRoutingError",
]


class TaskRoutingError(RuntimeError):
    """Router-level failures (no adapter matches, preferred unknown, ...)."""


class NoAdapterForCapabilities(TaskRoutingError):
    """Raised when no registered adapter satisfies the requested capabilities."""


class TaskAdapterError(RuntimeError):
    """Generic adapter-level failure (subprocess crash, transport, etc.)."""
