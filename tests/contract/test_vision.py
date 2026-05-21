"""Contract tests for ``VisionAdapter``.

Hermetic guard: only adapters whose ``name`` is in
:data:`HERMETIC_NAMES` run their full body. The factory contract
suite reuses the same parametrised fixture machinery as the other
contracts (see ``tests/contract/conftest.py``).

For M13, the hermetic set is ``{"mock"}``. ``MediaPipeVisionAdapter``
needs a real camera + the ``[mediapipe]`` extras, so it lives under
its own unit test (``test_mediapipe_adapter.py``) which stubs the
heavy dependencies.
"""

from __future__ import annotations

import pytest
from openmimicry.core.contracts import VisionAdapter
from openmimicry.core.schemas import VisionConfig

pytestmark = pytest.mark.contract


HERMETIC_NAMES: frozenset[str] = frozenset({"mock"})


def _is_hermetic(adapter) -> bool:
    return getattr(adapter, "name", "") in HERMETIC_NAMES


@pytest.mark.parametrize("implementations", ["vision"], indirect=True)
def test_vision_adapter_protocol_isinstance(implementations) -> None:
    if not implementations:
        pytest.skip("no VisionAdapter implementations registered")
    for name, factory in implementations:
        instance = factory()
        assert isinstance(instance, VisionAdapter), (
            f"{name!r} does not satisfy VisionAdapter Protocol"
        )


@pytest.mark.parametrize("implementations", ["vision"], indirect=True)
async def test_vision_adapter_healthcheck_returns_bool(implementations) -> None:
    if not implementations:
        pytest.skip("no VisionAdapter implementations registered")
    for _name, factory in implementations:
        instance = factory()
        assert isinstance(await instance.healthcheck(), bool)


@pytest.mark.parametrize("implementations", ["vision"], indirect=True)
async def test_start_stop_round_trip(implementations) -> None:
    if not implementations:
        pytest.skip("no VisionAdapter implementations registered")
    any_ran = False
    for _name, factory in implementations:
        instance = factory()
        if not _is_hermetic(instance):
            continue
        cfg = VisionConfig(enabled=True, require_consent=False)
        await instance.start(cfg)
        assert instance.is_running is True
        await instance.stop()
        assert instance.is_running is False
        any_ran = True
    if not any_ran:
        pytest.skip("no hermetic VisionAdapter implementations registered")


@pytest.mark.parametrize("implementations", ["vision"], indirect=True)
async def test_capabilities_is_set_of_strings(implementations) -> None:
    if not implementations:
        pytest.skip("no VisionAdapter implementations registered")
    for _name, factory in implementations:
        instance = factory()
        assert isinstance(instance.capabilities, set)
        for cap in instance.capabilities:
            assert isinstance(cap, str)
