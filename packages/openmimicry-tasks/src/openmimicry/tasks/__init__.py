"""openmimicry-tasks: TaskRouter, real adapters, mock fixture, intent detector.

Exports
-------

* :class:`TaskRuntimeAdapter` — re-exported Protocol.
* :class:`TaskRouter` — capability-based router; itself an adapter.
* :class:`MockTaskRuntimeAdapter` — canonical fixture.
* :class:`LocalShellAdapter`, :class:`ClaudeCodeAdapter`,
  :class:`MCPAgentAdapter` — concrete adapters.
* :class:`OpenClawAdapter`, :class:`PicoClawAdapter` — post-v0.2 stubs.
* :func:`detect_task_intent` — regex-first intent detector.
* :class:`TaskRoutingError`, :class:`NoAdapterForCapabilities`,
  :class:`TaskAdapterError`, :class:`TaskError`.
"""

from __future__ import annotations

from .adapters import (
    AllowlistEntry,
    ClaudeCodeAdapter,
    ClaudeCodeSettings,
    LocalShellAdapter,
    LocalShellSettings,
    MCPAgentAdapter,
    MCPAgentSettings,
    MCPAgentUnavailable,
    OpenClawAdapter,
    PicoClawAdapter,
    ShellNotAllowed,
)
from .base import TaskRuntimeAdapter
from .errors import (
    NoAdapterForCapabilities,
    TaskAdapterError,
    TaskError,
    TaskRoutingError,
)
from .intent import detect_task_intent
from .mocks import MockTaskRuntimeAdapter
from .router import TaskRouter

__all__ = [
    "AllowlistEntry",
    "ClaudeCodeAdapter",
    "ClaudeCodeSettings",
    "LocalShellAdapter",
    "LocalShellSettings",
    "MCPAgentAdapter",
    "MCPAgentSettings",
    "MCPAgentUnavailable",
    "MockTaskRuntimeAdapter",
    "NoAdapterForCapabilities",
    "OpenClawAdapter",
    "PicoClawAdapter",
    "ShellNotAllowed",
    "TaskAdapterError",
    "TaskError",
    "TaskRoutingError",
    "TaskRouter",
    "TaskRuntimeAdapter",
    "detect_task_intent",
]

__version__ = "0.2.0a0"
