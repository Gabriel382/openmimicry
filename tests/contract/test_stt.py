"""Contract tests for ``STTAdapter``.

Bodies skip until M2 lands. Fixture machinery is real: M2 registers
``RealtimeSTTAdapter`` under entry-point group ``openmimicry.contracts.stt``.
"""

from __future__ import annotations

import pytest
from openmimicry.core.contracts import STTAdapter

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("implementations", ["stt"], indirect=True)
def test_sttadapter_protocol_isinstance(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M2 (no STTAdapter implementations registered)")
    for name, factory in implementations:
        instance = factory()
        assert isinstance(instance, STTAdapter), f"{name!r} does not satisfy STTAdapter Protocol"


@pytest.mark.parametrize("implementations", ["stt"], indirect=True)
async def test_healthcheck_returns_bool(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M2")
    for _name, factory in implementations:
        instance = factory()
        assert isinstance(await instance.healthcheck(), bool)


@pytest.mark.parametrize("implementations", ["stt"], indirect=True)
async def test_start_stop_cycle(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M2")
    pytest.skip("M2 will provide a programmable mock for this assertion")


@pytest.mark.parametrize("implementations", ["stt"], indirect=True)
async def test_transcripts_property_returns_async_iter(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M2")
    pytest.skip("M2 will assert the async-iterator contract on transcripts")
