"""Contract tests for AvatarRuntimeAdapter.

Implementations register under entry-point group
``openmimicry.contracts.avatar_runtime``. M3 ships ``MockAvatarRuntimeAdapter``;
M4 will add ``Sprite2DAvatarAdapter``; M9 will add ``ThreeJSAvatarAdapter``;
post-v0.2 modalities add their own.

Hermetic checks run against ``name == "mock"``. Real runtimes that touch
audio / video / Unity / etc. are skipped via the same guard so the contract
suite stays offline.
"""

from __future__ import annotations

import pytest
from openmimicry.core.contracts import AvatarRuntimeAdapter
from openmimicry.core.schemas import AvatarDirective

pytestmark = pytest.mark.contract


def _is_hermetic(adapter) -> bool:
    return getattr(adapter, "name", "") == "mock"


@pytest.mark.parametrize("implementations", ["avatar_runtime"], indirect=True)
def test_avatarruntime_protocol_isinstance(implementations) -> None:
    if not implementations:
        pytest.skip("no AvatarRuntimeAdapter implementations registered")
    for name, factory in implementations:
        instance = factory()
        assert isinstance(instance, AvatarRuntimeAdapter), (
            f"{name!r} does not satisfy AvatarRuntimeAdapter Protocol"
        )


@pytest.mark.parametrize("implementations", ["avatar_runtime"], indirect=True)
async def test_healthcheck_returns_bool(implementations) -> None:
    if not implementations:
        pytest.skip("no AvatarRuntimeAdapter implementations registered")
    for _name, factory in implementations:
        instance = factory()
        assert isinstance(await instance.healthcheck(), bool)


@pytest.mark.parametrize("implementations", ["avatar_runtime"], indirect=True)
async def test_apply_directive_round_trip(implementations) -> None:
    """Adapters must accept any well-formed AvatarDirective without raising,
    including ones with fields they don't render (gesture/gaze/intensity)."""
    if not implementations:
        pytest.skip("no AvatarRuntimeAdapter implementations registered")
    any_ran = False
    for _name, factory in implementations:
        instance = factory()
        if not _is_hermetic(instance):
            continue
        await instance.load_character("test", {})
        await instance.apply_directive(AvatarDirective(state="listening"))
        await instance.apply_directive(
            AvatarDirective(
                state="happy",
                emotion="happy",
                gesture="wave",
                gaze="left",
                intensity=0.5,
            )
        )
        await instance.shutdown()
        any_ran = True
    if not any_ran:
        pytest.skip("no hermetic AvatarRuntimeAdapter implementations registered")


@pytest.mark.parametrize("implementations", ["avatar_runtime"], indirect=True)
async def test_shutdown_is_idempotent(implementations) -> None:
    if not implementations:
        pytest.skip("no AvatarRuntimeAdapter implementations registered")
    for _name, factory in implementations:
        instance = factory()
        await instance.shutdown()
        await instance.shutdown()


@pytest.mark.parametrize("implementations", ["avatar_runtime"], indirect=True)
async def test_capabilities_is_set_of_strings(implementations) -> None:
    if not implementations:
        pytest.skip("no AvatarRuntimeAdapter implementations registered")
    for _name, factory in implementations:
        instance = factory()
        assert isinstance(instance.capabilities, set)
        for cap in instance.capabilities:
            assert isinstance(cap, str)
