"""Live wake-listening flow.

We enable live wake on the speech controller, then push a transcript
starting with the configured wake name. The controller publishes
``UserSpeechFinal`` and the avatar director moves to ``listening``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from openmimicry.core import UserSpeechFinal

pytestmark = pytest.mark.integration


async def _collect_kind(bus, kind: str, *, timeout: float = 2.0):
    sub = bus.subscribe()
    collected: list = []

    async def _drain() -> None:
        async for event in sub:
            collected.append(event)
            if any(e.kind == kind for e in collected):
                return

    try:
        await asyncio.wait_for(_drain(), timeout=timeout)
    except asyncio.TimeoutError:
        pass
    return collected


async def test_live_wake_publishes_final_on_wake_match(wiring: Any) -> None:
    speech = wiring.speech
    stt = wiring.stt

    await speech.enable_live_listening(wake_names=["Mimi"])
    try:
        collector = asyncio.create_task(_collect_kind(wiring.bus, "speech_final"))
        await asyncio.sleep(0)

        # The mock STT doesn't actually filter by wake name — the live
        # listener just projects every final transcript.
        await stt.push_transcript("Mimi, what's the time?", is_final=True)

        events = await collector
        finals = [e for e in events if isinstance(e, UserSpeechFinal)]
        assert finals, "no UserSpeechFinal published in live-wake mode"
        assert "Mimi" in finals[-1].text
    finally:
        await speech.disable_live_listening()
