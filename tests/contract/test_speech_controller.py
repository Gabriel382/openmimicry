"""Contract tests for SpeechController.

Implementations register under entry-point group
``openmimicry.contracts.speech_controller``. The factory builds a fully
hermetic controller (mock STT + mock TTS + fresh EventBus) so the contract
suite stays offline.
"""

from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("implementations", ["speech_controller"], indirect=True)
async def test_start_stop_cycle(implementations) -> None:
    if not implementations:
        pytest.skip("no SpeechController implementations registered")
    for _name, factory in implementations:
        ctl = factory()
        await ctl.start()
        await ctl.stop()


@pytest.mark.parametrize("implementations", ["speech_controller"], indirect=True)
async def test_say_then_interrupt(implementations) -> None:
    if not implementations:
        pytest.skip("no SpeechController implementations registered")
    for _name, factory in implementations:
        ctl = factory()
        await ctl.start()
        try:
            await ctl.say("hello")
            # interrupt() must not raise even if speech has already finished.
            await ctl.interrupt()
        finally:
            await ctl.stop()


@pytest.mark.parametrize("implementations", ["speech_controller"], indirect=True)
async def test_ptt_open_close(implementations) -> None:
    if not implementations:
        pytest.skip("no SpeechController implementations registered")
    for _name, factory in implementations:
        ctl = factory()
        await ctl.start()
        try:
            await ctl.ptt_down()
            # No real microphone -> push a synthetic transcript via the mock.
            stt = getattr(ctl, "stt", None)
            if stt is not None and hasattr(stt, "push_transcript"):
                await stt.push_transcript("ping", is_final=True)
            await asyncio.wait_for(ctl.ptt_up(), timeout=2.0)
        finally:
            await ctl.stop()


@pytest.mark.parametrize("implementations", ["speech_controller"], indirect=True)
async def test_live_listening_toggle(implementations) -> None:
    if not implementations:
        pytest.skip("no SpeechController implementations registered")
    for _name, factory in implementations:
        ctl = factory()
        await ctl.start()
        try:
            await ctl.enable_live_listening(wake_names=["Mimi"])
            await ctl.disable_live_listening()
        finally:
            await ctl.stop()
