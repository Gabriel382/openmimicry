"""Contract tests for ``TaskRuntimeAdapter``.

Bodies skip until M5 lands.
"""

from __future__ import annotations

import pytest
from openmimicry.core.contracts import TaskRuntimeAdapter

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("implementations", ["task_runtime"], indirect=True)
def test_taskruntime_protocol_isinstance(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M5 (no TaskRuntimeAdapter implementations registered)")
    for name, factory in implementations:
        instance = factory()
        assert isinstance(instance, TaskRuntimeAdapter), (
            f"{name!r} does not satisfy TaskRuntimeAdapter Protocol"
        )


@pytest.mark.parametrize("implementations", ["task_runtime"], indirect=True)
async def test_healthcheck_returns_bool(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M5")
    for _name, factory in implementations:
        instance = factory()
        assert isinstance(await instance.healthcheck(), bool)


@pytest.mark.parametrize("implementations", ["task_runtime"], indirect=True)
async def test_submit_returns_handle(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M5")
    pytest.skip("M5 will provide a scripted-mock fixture for submit/handle assertions")


@pytest.mark.parametrize("implementations", ["task_runtime"], indirect=True)
async def test_updates_yields_terminal_status(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M5")
    pytest.skip("M5 will assert updates() reaches a terminal status name")


@pytest.mark.parametrize("implementations", ["task_runtime"], indirect=True)
async def test_cancel_is_idempotent(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M5")
    pytest.skip("M5 will assert cancel() is a no-op on terminal tasks")
