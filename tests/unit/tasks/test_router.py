"""Unit tests for TaskRouter — selection algorithm + dispatch."""

from __future__ import annotations

import pytest
from openmimicry.core.schemas.tasks import TaskRequest
from openmimicry.tasks.errors import NoAdapterForCapabilities, TaskRoutingError
from openmimicry.tasks.mocks import MockTaskRuntimeAdapter
from openmimicry.tasks.router import TaskRouter


class _CapAdapter(MockTaskRuntimeAdapter):
    """A mock adapter with a custom name + capabilities."""

    def __init__(self, name: str, caps: set[str]) -> None:
        super().__init__(step_delay_s=0.0)
        self._custom_name = name
        self._caps = set(caps)

    @property
    def name(self) -> str:  # type: ignore[override]
        return self._custom_name

    @property
    def capabilities(self) -> set[str]:  # type: ignore[override]
        return self._caps


def test_router_rejects_empty_adapter_set() -> None:
    with pytest.raises(TaskRoutingError):
        TaskRouter(adapters={})


def test_router_rejects_unknown_default_runtime() -> None:
    with pytest.raises(TaskRoutingError):
        TaskRouter(adapters={"a": MockTaskRuntimeAdapter()}, default_runtime="b")


def test_select_preferred_wins() -> None:
    primary = MockTaskRuntimeAdapter()
    fallback = MockTaskRuntimeAdapter()
    router = TaskRouter(
        adapters={"primary": primary, "fallback": fallback},
        default_runtime="fallback",
    )
    chosen = router.select(
        TaskRequest(summary="s", instructions="i", preferred_runtime="primary")
    )
    assert chosen is primary


def test_select_capability_superset() -> None:
    code = _CapAdapter("claude_code", {"code", "text"})
    shell = _CapAdapter("local_shell", {"shell"})
    router = TaskRouter(adapters={"claude_code": code, "local_shell": shell})
    chosen = router.select(
        TaskRequest(
            summary="s", instructions="i", capabilities_required={"code"}
        )
    )
    assert chosen is code


def test_select_falls_back_to_default() -> None:
    a = _CapAdapter("a", {"x"})
    b = MockTaskRuntimeAdapter()
    router = TaskRouter(adapters={"a": a, "mock": b}, default_runtime="mock")
    # No capability match for "y"; no preferred; falls back to default.
    chosen = router.select(
        TaskRequest(
            summary="s", instructions="i", capabilities_required={"y"}
        )
    )
    assert chosen is b


def test_select_no_match_raises() -> None:
    a = _CapAdapter("a", {"x"})
    router = TaskRouter(adapters={"a": a})
    with pytest.raises(NoAdapterForCapabilities):
        router.select(
            TaskRequest(
                summary="s", instructions="i", capabilities_required={"y"}
            )
        )


def test_unknown_preferred_falls_through_to_capability_match() -> None:
    code = _CapAdapter("claude_code", {"code"})
    router = TaskRouter(adapters={"claude_code": code})
    chosen = router.select(
        TaskRequest(
            summary="s",
            instructions="i",
            preferred_runtime="unknown",
            capabilities_required={"code"},
        )
    )
    assert chosen is code


async def test_submit_remembers_handle_runtime() -> None:
    a = MockTaskRuntimeAdapter(step_delay_s=0.0)
    b = MockTaskRuntimeAdapter(step_delay_s=0.0)
    router = TaskRouter(adapters={"a": a, "b": b}, default_runtime="a")
    handle = await router.submit(
        TaskRequest(summary="s", instructions="i", preferred_runtime="b")
    )
    # The router should route status/updates/result to the same adapter.
    status = await router.status(handle)
    assert status.handle.id == handle.id
    async for _ in router.updates(handle):
        pass
    result = await router.result(handle)
    assert result.status == "succeeded"


async def test_cancel_dispatches_to_owning_adapter() -> None:
    a = MockTaskRuntimeAdapter(step_delay_s=0.1)
    router = TaskRouter(adapters={"a": a}, default_runtime="a")
    handle = await router.submit(
        TaskRequest(summary="s", instructions="i", preferred_runtime="a")
    )
    await router.cancel(handle)
    received = [upd async for upd in router.updates(handle)]
    assert received[-1].status == "cancelled"


async def test_healthcheck_or_logic() -> None:
    a = MockTaskRuntimeAdapter()
    router = TaskRouter(adapters={"a": a})
    assert await router.healthcheck() is True


def test_capabilities_is_union() -> None:
    code = _CapAdapter("claude_code", {"code"})
    shell = _CapAdapter("local_shell", {"shell"})
    router = TaskRouter(adapters={"claude_code": code, "local_shell": shell})
    assert router.capabilities == {"code", "shell"}
