"""Contract tests for ``SpeechController``.

Bodies skip until M2 lands.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("implementations", ["speech_controller"], indirect=True)
async def test_start_stop_cycle(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M2 (no SpeechController implementations registered)")
    for _name, factory in implementations:
        instance = factory()
        await instance.start()
        await instance.stop()


@pytest.mark.parametrize("implementations", ["speech_controller"], indirect=True)
async def test_say_then_interrupt(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M2")
    pytest.skip("M2 will wire mock STT + mock TTS to assert barge-in behaviour")


@pytest.mark.parametrize("implementations", ["speech_controller"], indirect=True)
async def test_ptt_open_close(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M2")
    pytest.skip("M2 will assert ptt_down/ptt_up cycle integrates with mock STT")


@pytest.mark.parametrize("implementations", ["speech_controller"], indirect=True)
async def test_live_listening_toggle(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M2")
    pytest.skip("M2 will assert enable_live_listening/disable_live_listening")
