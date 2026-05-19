"""Unit tests for detect_task_intent."""

from __future__ import annotations

import pytest
from openmimicry.tasks.intent import detect_task_intent


def test_ask_claude_returns_claude_code_intent() -> None:
    req = detect_task_intent("Ask Claude to refactor utils.py")
    assert req is not None
    assert req.preferred_runtime == "claude_code"
    assert "refactor utils.py" in req.instructions
    assert "code" in req.capabilities_required


def test_ask_claude_code_returns_claude_code_intent() -> None:
    req = detect_task_intent("Ask Claude Code to fix the failing test")
    assert req is not None
    assert req.preferred_runtime == "claude_code"


def test_send_this_to_claude_returns_claude_code_intent() -> None:
    req = detect_task_intent("Send this to Claude: write a docstring")
    assert req is not None
    assert req.preferred_runtime == "claude_code"


def test_use_mcp_agent_returns_mcp_intent() -> None:
    req = detect_task_intent("Use the MCP agent to inspect the repo")
    assert req is not None
    assert req.preferred_runtime == "mcp_agent"
    assert "mcp" in req.capabilities_required


def test_run_shell_returns_local_shell_intent() -> None:
    req = detect_task_intent("Run the shell to list files in /tmp")
    assert req is not None
    assert req.preferred_runtime == "local_shell"


def test_plain_chat_returns_none() -> None:
    assert detect_task_intent("What is the speed of light?") is None
    assert detect_task_intent("hello there") is None


def test_empty_input_returns_none() -> None:
    assert detect_task_intent("") is None
    assert detect_task_intent("   ") is None


def test_summary_truncates_long_lines() -> None:
    long_instr = "Ask Claude to " + ("do something very specific " * 10)
    req = detect_task_intent(long_instr)
    assert req is not None
    assert len(req.summary) <= 80
