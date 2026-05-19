"""Contract tests for ``TaskRuntimeAdapter``.

The hermetic guard restricts the run to adapters that have no external
prerequisites in CI. Right now that's ``mock``; ``local_shell`` could be
admitted but is gated behind ``RUN_LOCAL_SHELL_CONTRACT=1`` because it
spawns real subprocesses. The remaining adapters (``claude_code``,
``mcp_agent``) require credentials or optional packages and are exercised
in their dedicated unit tests via fakes.
"""

from __future__ import annotations

import os

import pytest
from openmimicry.core.contracts import TaskRuntimeAdapter
from openmimicry.core.schemas.tasks import TaskRequest

pytestmark = pytest.mark.contract


_DEFAULT_HERMETIC: frozenset[str] = frozenset({"mock"})


def _hermetic_names() -> frozenset[str]:
    names = set(_DEFAULT_HERMETIC)
    if os.environ.get("RUN_LOCAL_SHELL_CONTRACT") == "1":
        names.add("local_shell")
    return frozenset(names)


def _hermetic(implementations):
    allowed = _hermetic_names()
    return [(name, factory) for (name, factory) in implementations if name in allowed]


@pytest.mark.parametrize("implementations", ["task_runtime"], indirect=True)
def test_taskruntime_protocol_isinstance(implementations) -> None:
    impls = _hermetic(implementations)
    if not impls:
        pytest.skip("no hermetic TaskRuntimeAdapter implementations registered")
    for name, factory in impls:
        instance = factory()
        assert isinstance(instance, TaskRuntimeAdapter), (
            f"{name!r} does not satisfy TaskRuntimeAdapter Protocol"
        )


@pytest.mark.parametrize("implementations", ["task_runtime"], indirect=True)
async def test_healthcheck_returns_bool(implementations) -> None:
    impls = _hermetic(implementations)
    if not impls:
        pytest.skip("no hermetic implementations")
    for _name, factory in impls:
        instance = factory()
        assert isinstance(await instance.healthcheck(), bool)


@pytest.mark.parametrize("implementations", ["task_runtime"], indirect=True)
async def test_submit_returns_handle(implementations) -> None:
    impls = _hermetic(implementations)
    if not impls:
        pytest.skip("no hermetic implementations")
    for name, factory in impls:
        instance = factory()
        request = _request_for(name)
        handle = await instance.submit(request)
        assert handle.id, f"{name!r}: empty TaskHandle.id"
        assert handle.runtime, f"{name!r}: empty TaskHandle.runtime"


@pytest.mark.parametrize("implementations", ["task_runtime"], indirect=True)
async def test_updates_yields_terminal_status(implementations) -> None:
    impls = _hermetic(implementations)
    if not impls:
        pytest.skip("no hermetic implementations")
    terminal = {"succeeded", "failed", "cancelled"}
    for name, factory in impls:
        instance = factory()
        request = _request_for(name)
        handle = await instance.submit(request)
        received = [upd async for upd in instance.updates(handle)]
        assert received, f"{name!r}: updates() yielded nothing"
        assert received[-1].status in terminal, (
            f"{name!r}: final status {received[-1].status!r} not terminal"
        )


@pytest.mark.parametrize("implementations", ["task_runtime"], indirect=True)
async def test_cancel_is_idempotent(implementations) -> None:
    impls = _hermetic(implementations)
    if not impls:
        pytest.skip("no hermetic implementations")
    for name, factory in impls:
        instance = factory()
        request = _request_for(name)
        handle = await instance.submit(request)
        # Drain to terminal first.
        _ = [upd async for upd in instance.updates(handle)]
        # Now cancel() should be a no-op (no exception).
        await instance.cancel(handle)
        await instance.cancel(handle)


def _request_for(name: str) -> TaskRequest:
    """Per-adapter benign request shape."""
    if name == "local_shell":
        # The unit suite exercises argv validation; here we send a trivial
        # echo. CI gates this branch behind RUN_LOCAL_SHELL_CONTRACT=1 so
        # an allowlist for `echo` must be wired by the test environment.
        return TaskRequest(
            summary="contract echo",
            instructions="echo openmimicry",
            metadata={"argv": ["echo", "openmimicry"]},
        )
    return TaskRequest(summary="contract", instructions="noop")
