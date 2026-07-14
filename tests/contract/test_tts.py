"""Contract tests for TTSAdapter.

Implementations register under entry-point group ``openmimicry.contracts.tts``.
M2 ships MockTTSAdapter (always hermetic) and RealtimeTTSAdapter (skipped
unless RealtimeTTS is installed).
"""

from __future__ import annotations

import asyncio

import pytest
from openmimicry.core.contracts import TTSAdapter
from openmimicry.core.schemas import TTSConfig

pytestmark = pytest.mark.contract


def _is_hermetic(adapter) -> bool:
    return getattr(adapter, "name", "") == "mock-tts"


@pytest.mark.parametrize("implementations", ["tts"], indirect=True)
def test_ttsadapter_protocol_isinstance(implementations) -> None:
    if not implementations:
        pytest.skip("no TTSAdapter implementations registered")
    for name, factory in implementations:
        instance = factory()
        assert isinstance(instance, TTSAdapter), f"{name!r} does not satisfy TTSAdapter Protocol"


@pytest.mark.parametrize("implementations", ["tts"], indirect=True)
async def test_healthcheck_returns_bool(implementations) -> None:
    if not implementations:
        pytest.skip("no TTSAdapter implementations registered")
    for _name, factory in implementations:
        instance = factory()
        assert isinstance(await instance.healthcheck(), bool)


@pytest.mark.parametrize("implementations", ["tts"], indirect=True)
async def test_stop_is_idempotent(implementations) -> None:
    if not implementations:
        pytest.skip("no TTSAdapter implementations registered")
    for _name, factory in implementations:
        instance = factory()
        if not _is_hermetic(instance):
            continue
        await instance.stop()
        await instance.stop()


@pytest.mark.parametrize("implementations", ["tts"], indirect=True)
async def test_speak_string_completes(implementations) -> None:
    if not implementations:
        pytest.skip("no TTSAdapter implementations registered")
    any_ran = False
    for _name, factory in implementations:
        instance = factory()
        if not _is_hermetic(instance):
            continue
        await asyncio.wait_for(instance.speak("hello", config=TTSConfig()), timeout=1.0)
        any_ran = True
    if not any_ran:
        pytest.skip("no hermetic TTSAdapter implementations registered")
