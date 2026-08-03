"""Persistence and lifecycle tests for the provider-neutral task journal."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from openmimicry.core.schemas.tasks import TaskHandle, TaskRequest, TaskUpdate
from openmimicry.tasks import JournaledTaskRuntime, TaskJournal
from openmimicry.tasks.mocks import MockTaskRuntimeAdapter


def test_unfinished_task_is_interrupted_after_reopen(tmp_path) -> None:
    path = tmp_path / "tasks.sqlite3"
    journal = TaskJournal(str(path))
    handle = TaskHandle(id="pending-task", runtime="mock")
    journal.record_submission(
        handle,
        TaskRequest(summary="pending", instructions="still running"),
    )
    journal.close()

    reopened = TaskJournal(str(path))
    assert reopened.get_task(handle.id)["status"] == "interrupted"
    reopened.close()


async def test_journaled_runtime_persists_terminal_result_and_notification(tmp_path) -> None:
    runtime = JournaledTaskRuntime(
        MockTaskRuntimeAdapter(step_delay_s=0.0),
        TaskJournal(str(tmp_path / "tasks.sqlite3")),
    )
    handle = await runtime.submit(TaskRequest(summary="test", instructions="finish"))
    updates = [update async for update in runtime.updates(handle)]
    result = await runtime.result(handle)

    assert updates[-1].status == "succeeded"
    assert result.status == "succeeded"
    assert runtime.journal.get_task(handle.id)["status"] == "succeeded"
    assert runtime.journal.list_notifications()[0]["task_id"] == handle.id
    await runtime.close()


async def test_close_marks_live_monitor_interrupted(tmp_path) -> None:
    placeholder = TaskHandle(id="placeholder", runtime="mock")
    runtime = JournaledTaskRuntime(
        MockTaskRuntimeAdapter(
            scripted_updates=[
                TaskUpdate(
                    handle=placeholder,
                    status="running",
                    ts=datetime.now(timezone.utc),
                )
            ],
            step_delay_s=1.0,
        ),
        TaskJournal(str(tmp_path / "tasks.sqlite3")),
    )
    handle = await runtime.submit(TaskRequest(summary="long", instructions="wait"))
    await asyncio.sleep(0)
    await runtime.close()

    reopened = TaskJournal(str(tmp_path / "tasks.sqlite3"))
    assert reopened.get_task(handle.id)["status"] == "interrupted"
    reopened.close()


async def test_fast_terminal_updates_are_replayed_to_late_subscriber(tmp_path) -> None:
    runtime = JournaledTaskRuntime(
        MockTaskRuntimeAdapter(step_delay_s=0.0),
        TaskJournal(str(tmp_path / "tasks.sqlite3")),
    )
    handle = await runtime.submit(TaskRequest(summary="fast", instructions="finish now"))
    monitor = runtime._monitors[handle.id]  # type: ignore[attr-defined]
    await monitor

    updates = [update async for update in runtime.updates(handle)]

    assert updates
    assert updates[-1].status == "succeeded"
    assert runtime.journal.get_task(handle.id)["status"] == "succeeded"
    await runtime.close()
