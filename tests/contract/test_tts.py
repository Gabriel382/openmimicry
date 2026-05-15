"""Contract tests for ``TTSAdapter``.

Bodies skip until M2 lands.
"""

from __future__ import annotations

import pytest
from openmimicry.core.contracts import TTSAdapter

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("implementations", ["tts"], indirect=True)
def test_ttsadapter_protocol_isinstance(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M2 (no TTSAdapter implementations registered)")
    for name, factory in implementations:
        instance = factory()
        assert isinstance(instance, TTSAdapter), f"{name!r} does not satisfy TTSAdapter Protocol"


@pytest.mark.parametrize("implementations", ["tts"], indirect=True)
async def test_healthcheck_returns_bool(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M2")
    for _name, factory in implementations:
        instance = factory()
        assert isinstance(await instance.healthcheck(), bool)


@pytest.mark.parametrize("implementations", ["tts"], indirect=True)
async def test_stop_is_idempotent(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M2")
    for _name, factory in implementations:
        instance = factory()
        await instance.stop()
        await instance.stop()


@pytest.mark.parametrize("implementations", ["tts"], indirect=True)
async def test_speak_string_completes(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M2")
    pytest.skip("M2 will provide a recording mock for this assertion")
