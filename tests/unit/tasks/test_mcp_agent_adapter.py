"""Unit tests for MCPAgentAdapter.

`mcp-agent` is not a test dependency. We inject a fake `mcp_agent` module
via `sys.modules` so the adapter exercises its full code path against a
synthetic agent run.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest
from openmimicry.core.contracts import TaskRuntimeAdapter
from openmimicry.core.schemas.tasks import TaskRequest
from openmimicry.tasks.adapters.mcp_agent_adapter import (
    MCPAgentAdapter,
    MCPAgentUnavailable,
)


class _FakeAgent:
    """Minimal agent shape: instantiable + .run() returns an async iterator."""

    def __init__(self, *, instructions: str, servers: list[Any]) -> None:
        self.instructions = instructions
        self.servers = servers
        self.cancelled: bool = False

    async def _events(self):
        for note in ("starting", "step 1", "step 2", "done"):
            yield types.SimpleNamespace(note=note)

    def run(self):
        return self._events()

    def cancel(self) -> None:
        self.cancelled = True


def _install_fake_mcp(monkeypatch: pytest.MonkeyPatch, agent_cls=_FakeAgent) -> None:
    fake = types.SimpleNamespace(Agent=agent_cls)
    monkeypatch.setitem(sys.modules, "mcp_agent", fake)


async def test_unavailable_when_mcp_agent_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "mcp_agent", raising=False)
    monkeypatch.setattr(
        "openmimicry.tasks.adapters.mcp_agent_adapter._import_mcp_agent",
        lambda: (_ for _ in ()).throw(MCPAgentUnavailable("missing")),
    )
    adapter = MCPAgentAdapter()
    assert await adapter.healthcheck() is False
    handle = await adapter.submit(TaskRequest(summary="s", instructions="i"))
    received = [upd async for upd in adapter.updates(handle)]
    assert received[-1].status == "failed"
    assert "mcp_agent_missing" in (received[-1].error.code if received[-1].error else "")


def test_mcp_satisfies_protocol() -> None:
    assert isinstance(MCPAgentAdapter(), TaskRuntimeAdapter)


async def test_run_streams_events_to_task_updates(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_mcp(monkeypatch)
    adapter = MCPAgentAdapter()
    handle = await adapter.submit(TaskRequest(summary="s", instructions="inspect repo"))
    received = [upd async for upd in adapter.updates(handle)]
    notes = [u.note for u in received if u.note]
    assert "step 1" in notes
    assert "step 2" in notes
    assert received[-1].status == "succeeded"


async def test_cancel_marks_run_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    class _SlowAgent(_FakeAgent):
        async def _events(self):
            for note in ("step 1", "step 2", "step 3"):
                await asyncio.sleep(0.05)
                if self.cancelled:
                    return
                yield types.SimpleNamespace(note=note)

    _install_fake_mcp(monkeypatch, agent_cls=_SlowAgent)
    adapter = MCPAgentAdapter()
    handle = await adapter.submit(TaskRequest(summary="s", instructions="long task"))
    # Let one event flow, then cancel.
    await asyncio.sleep(0.06)
    await adapter.cancel(handle)
    received = [upd async for upd in adapter.updates(handle)]
    assert received[-1].status == "cancelled"
    result = await adapter.result(handle)
    assert result.status == "cancelled"


async def test_run_handles_exception_as_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BoomAgent(_FakeAgent):
        async def _events(self):
            yield types.SimpleNamespace(note="step 1")
            raise RuntimeError("mcp blew up")

    _install_fake_mcp(monkeypatch, agent_cls=_BoomAgent)
    adapter = MCPAgentAdapter()
    handle = await adapter.submit(TaskRequest(summary="s", instructions="x"))
    received = [upd async for upd in adapter.updates(handle)]
    assert received[-1].status == "failed"
