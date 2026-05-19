"""Concrete TaskRuntimeAdapter implementations."""

from __future__ import annotations

from .claude_code_adapter import ClaudeCodeAdapter, ClaudeCodeSettings
from .local_shell_adapter import (
    AllowlistEntry,
    LocalShellAdapter,
    LocalShellSettings,
    ShellNotAllowed,
)
from .mcp_agent_adapter import MCPAgentAdapter, MCPAgentSettings, MCPAgentUnavailable
from .openclaw_adapter import OpenClawAdapter
from .picoclaw_adapter import PicoClawAdapter

__all__ = [
    "AllowlistEntry",
    "ClaudeCodeAdapter",
    "ClaudeCodeSettings",
    "LocalShellAdapter",
    "LocalShellSettings",
    "MCPAgentAdapter",
    "MCPAgentSettings",
    "MCPAgentUnavailable",
    "OpenClawAdapter",
    "PicoClawAdapter",
    "ShellNotAllowed",
]
