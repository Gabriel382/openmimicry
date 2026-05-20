"""Contract tests for AvatarRuntimeAdapter.

Implementations register under entry-point group
``openmimicry.contracts.avatar_runtime``. M3 ships ``MockAvatarRuntimeAdapter``;
M4 ships ``Sprite2DAvatarAdapter``; M9 ships ``ThreeJSAvatarAdapter``;
post-v0.2 modalities add their own.

Hermetic checks run against adapters whose ``name`` is in
:data:`HERMETIC_NAMES`. Real runtimes that touch audio / video / Unity /
etc. are skipped via the same guard so the contract suite stays
offline.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from openmimicry.core.contracts import AvatarRuntimeAdapter
from openmimicry.core.schemas import AvatarDirective

pytestmark = pytest.mark.contract


HERMETIC_NAMES: frozenset[str] = frozenset(
    {"mock", "sprite2d", "threejs", "live3d", "unity"}
)

# Pack used to drive `load_character` for the file-backed adapters. The
# fixture pack is `kind: sprite2d`; ThreeJS logs a warning about the
# mismatch but accepts the load (M9 brief: "never raise").
_PACK_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "packs" / "good_pack"
)


def _is_hermetic(adapter) -> bool:
    """Adapters that don't touch real renderers / hardware / network."""
    return getattr(adapter, "name", "") in HERMETIC_NAMES


def _load_config_for(adapter) -> dict:
    """Return a config dict so ``load_character`` can find a real pack."""
    name = getattr(adapter, "name", "")
    if name == "mock":
        return {}
    if name == "unity":
        # Unity doesn't read from disk — it sends the id + asset URL
        # over the wire. The mock transport accepts the frame.
        return {"asset_url": "https://example.invalid/character.fbx"}
    return {"pack_path": str(_PACK_FIXTURE_PATH)}


def _character_id_for(adapter) -> str:
    name = getattr(adapter, "name", "")
    if name == "mock":
        return "test"
    if name == "unity":
        return "test"
    return "good_pack"


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
        await instance.load_character(_character_id_for(instance), _load_config_for(instance))
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
