"""Contract tests for STTAdapter.

Implementations register under entry-point group ``openmimicry.contracts.stt``.
M2 ships MockSTTAdapter (always hermetic) and RealtimeSTTAdapter (skipped
unless RealtimeSTT is installed).
"""

from __future__ import annotations

import pytest
from openmimicry.core.contracts import STTAdapter
from openmimicry.core.schemas import STTConfig

pytestmark = pytest.mark.contract


def _is_hermetic(adapter) -> bool:
    """Only call start/stop on adapters that don't touch real hardware."""
    return getattr(adapter, "name", "") == "mock-stt"


@pytest.mark.parametrize("implementations", ["stt"], indirect=True)
def test_sttadapter_protocol_isinstance(implementations) -> None:
    if not implementations:
        pytest.skip("no STTAdapter implementations registered")
    for name, factory in implementations:
        instance = factory()
        assert isinstance(instance, STTAdapter), f"{name!r} does not satisfy STTAdapter Protocol"


@pytest.mark.parametrize("implementations", ["stt"], indirect=True)
async def test_healthcheck_returns_bool(implementations) -> None:
    if not implementations:
        pytest.skip("no STTAdapter implementations registered")
    for _name, factory in implementations:
        instance = factory()
        assert isinstance(await instance.healthcheck(), bool)


@pytest.mark.parametrize("implementations", ["stt"], indirect=True)
async def test_start_stop_cycle(implementations) -> None:
    if not implementations:
        pytest.skip("no STTAdapter implementations registered")
    any_ran = False
    for _name, factory in implementations:
        instance = factory()
        if not _is_hermetic(instance):
            continue
        await instance.start(STTConfig())
        await instance.stop()
        any_ran = True
    if not any_ran:
        pytest.skip("no hermetic STTAdapter implementations registered")


@pytest.mark.parametrize("implementations", ["stt"], indirect=True)
async def test_transcripts_property_returns_async_iter(implementations) -> None:
    if not implementations:
        pytest.skip("no STTAdapter implementations registered")
    any_ran = False
    for _name, factory in implementations:
        instance = factory()
        if not _is_hermetic(instance):
            continue
        await instance.start(STTConfig())
        it = instance.transcripts
        assert hasattr(it, "__aiter__")
        await instance.stop()
        any_ran = True
    if not any_ran:
        pytest.skip("no hermetic STTAdapter implementations registered")
