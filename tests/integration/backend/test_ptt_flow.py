"""Push-to-talk flow against the SpeechController + mock STT.

We drive :class:`MockSTTAdapter` directly because the FastAPI WS surface
is hard to script in TestClient (it requires the inbound JSON and an
async draining loop). The ``ptt.down`` / ``ptt.up`` inbound messages are
exercised in the WS unit test below; the actual STT bridging is what
matters here.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from openmimicry.core import UserSpeechFinal, UserSpeechStarted

pytestmark = pytest.mark.integration


async def _collect(bus, kinds: set[str], *, timeout: float = 2.0):
    collected: list = []
    sub = bus.subscribe()

    async def _drain() -> None:
        async for event in sub:
            collected.append(event)
            if not (kinds - {e.kind for e in collected}):
                return

    try:
        await asyncio.wait_for(_drain(), timeout=timeout)
    except asyncio.TimeoutError:
        pass
    return collected


async def test_ptt_publishes_started_and_final(wiring: Any) -> None:
    bus = wiring.bus
    stt = wiring.stt
    speech = wiring.speech

    collector = asyncio.create_task(_collect(bus, {"speech_start", "speech_final"}))
    await asyncio.sleep(0)

    await speech.ptt_down()
    # Push a final transcript onto the mock STT stream.
    await stt.push_transcript("hello from ptt", is_final=True)
    await speech.ptt_up()

    events = await collector

    started = [e for e in events if isinstance(e, UserSpeechStarted)]
    finals = [e for e in events if isinstance(e, UserSpeechFinal)]
    assert started, "no UserSpeechStarted on ptt_down"
    assert finals, "no UserSpeechFinal on ptt_up"
    assert finals[-1].text == "hello from ptt"
