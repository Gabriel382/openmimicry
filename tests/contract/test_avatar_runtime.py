"""Contract tests for ``AvatarRuntimeAdapter``.

Bodies skip until M3 (mocks) / M4 (Sprite2D) / M9 (Three.js) land.
"""

from __future__ import annotations

import pytest
from openmimicry.core.contracts import AvatarRuntimeAdapter

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("implementations", ["avatar_runtime"], indirect=True)
def test_avatarruntime_protocol_isinstance(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M3 (no AvatarRuntimeAdapter implementations registered)")
    for name, factory in implementations:
        instance = factory()
        assert isinstance(instance, AvatarRuntimeAdapter), (
            f"{name!r} does not satisfy AvatarRuntimeAdapter Protocol"
        )


@pytest.mark.parametrize("implementations", ["avatar_runtime"], indirect=True)
async def test_healthcheck_returns_bool(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M3")
    for _name, factory in implementations:
        instance = factory()
        assert isinstance(await instance.healthcheck(), bool)


@pytest.mark.parametrize("implementations", ["avatar_runtime"], indirect=True)
async def test_apply_directive_round_trip(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M3")
    pytest.skip("M3 will provide a recording mock; M4 asserts Sprite2D directives")


@pytest.mark.parametrize("implementations", ["avatar_runtime"], indirect=True)
async def test_shutdown_is_idempotent(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M3")
    for _name, factory in implementations:
        instance = factory()
        await instance.shutdown()
        await instance.shutdown()


@pytest.mark.parametrize("implementations", ["avatar_runtime"], indirect=True)
async def test_capabilities_is_set_of_strings(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M3")
    for _name, factory in implementations:
        instance = factory()
        assert isinstance(instance.capabilities, set)
        for cap in instance.capabilities:
            assert isinstance(cap, str)
