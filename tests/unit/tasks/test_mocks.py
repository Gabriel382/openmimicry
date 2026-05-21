"""Unit tests for MockTaskRuntimeAdapter."""

from __future__ import annotations

from datetime import datetime, timezone

from openmimicry.core.contracts import TaskRuntimeAdapter
from openmimicry.core.schemas.tasks import (
    TaskHandle,
    TaskRequest,
    TaskUpdate,
)
from openmimicry.tasks.mocks import MockTaskRuntimeAdapter


def _ts() -> datetime:
    return datetime.now(timezone.utc)


def test_mock_satisfies_protocol() -> None:
    assert isinstance(MockTaskRuntimeAdapter(), TaskRuntimeAdapter)


async def test_submit_returns_handle() -> None:
    adapter = MockTaskRuntimeAdapter()
    handle = await adapter.submit(TaskRequest(summary="x", instructions="x"))
    assert isinstance(handle, TaskHandle)
    assert handle.runtime == "mock"
    assert handle.id


async def test_updates_yields_scripted_then_terminal() -> None:
    placeholder = TaskHandle(id="will-be-rebound", runtime="mock")
    script = [
        TaskUpdate(handle=placeholder, status="queued", ts=_ts()),
        TaskUpdate(handle=placeholder, status="running", ts=_ts(), note="step 1"),
    ]
    adapter = MockTaskRuntimeAdapter(scripted_updates=script, step_delay_s=0.0)
    handle = await adapter.submit(TaskRequest(summary="s", instructions="i"))
    received = [upd async for upd in adapter.updates(handle)]
    statuses = [u.status for u in received]
    assert statuses[0] == "queued"
    assert "running" in statuses
    # Terminal succeeded auto-appended because the script didn't include one.
    assert statuses[-1] == "succeeded"
    # Handles are rebound to the live one.
    assert all(u.handle.id == handle.id for u in received)


async def test_cancel_yields_cancelled_status() -> None:
    placeholder = TaskHandle(id="x", runtime="mock")
    script = [TaskUpdate(handle=placeholder, status="running", ts=_ts())] * 10
    adapter = MockTaskRuntimeAdapter(scripted_updates=script, step_delay_s=0.05)
    handle = await adapter.submit(TaskRequest(summary="s", instructions="i"))
    await adapter.cancel(handle)
    received = [upd async for upd in adapter.updates(handle)]
    assert received[-1].status == "cancelled"


async def test_result_returns_terminal_status() -> None:
    adapter = MockTaskRuntimeAdapter(step_delay_s=0.0)
    handle = await adapter.submit(TaskRequest(summary="s", instructions="i"))
    # Drain the stream so the producer completes.
    async for _ in adapter.updates(handle):
        pass
    result = await adapter.result(handle)
    assert result.status == "succeeded"
    assert result.handle.id == handle.id


async def test_status_unknown_handle_returns_failed() -> None:
    adapter = MockTaskRuntimeAdapter()
    bogus = TaskHandle(id="not-a-handle", runtime="mock")
    status = await adapter.status(bogus)
    assert status.status == "failed"


async def test_healthcheck_returns_bool() -> None:
    assert isinstance(await MockTaskRuntimeAdapter().healthcheck(), bool)
