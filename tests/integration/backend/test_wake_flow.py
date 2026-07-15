"""Live wake-listening flow.

We enable live wake on the speech controller, then push a transcript
starting with the configured wake name. The controller publishes
``UserSpeechFinal`` and the avatar director moves to ``listening``.
"""

from __future__ import annotations

import asyncio
import contextlib
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

    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(_drain(), timeout=timeout)
    return collected


async def test_live_wake_publishes_final_on_wake_match(wiring: Any) -> None:
    speech = wiring.speech
    stt = wiring.stt

    await speech.enable_live_listening(wake_names=["Mimi"])
    try:
        collector = asyncio.create_task(_collect_kind(wiring.bus, "speech_final"))
        await asyncio.sleep(0)

        await stt.push_transcript("Mimi, what's the time?", is_final=True)

        events = await collector
        finals = [e for e in events if isinstance(e, UserSpeechFinal)]
        assert finals, "no UserSpeechFinal published in live-wake mode"
        assert finals[-1].text == "what's the time?"
    finally:
        await speech.disable_live_listening()
