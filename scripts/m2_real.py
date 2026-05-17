# scripts/m2_real.py (you can drop this in alongside m2_demo.py)
import asyncio
from openmimicry.core.bus import EventBus
from openmimicry.voice import (
    RealtimeSTTAdapter, RealtimeTTSAdapter, SpeechController,
)

async def main():
    bus = EventBus()
    stt = RealtimeSTTAdapter()
    tts = RealtimeTTSAdapter()
    ctl = SpeechController(stt=stt, tts=tts, bus=bus)
    await ctl.start()
    try:
        await ctl.say("Hello! I am listening.")
        # The controller's barge-in watcher is already running. Speak into
        # the mic; if you talk while it's speaking, TTS gets interrupted.
        await ctl.enable_live_listening(wake_names=["Mimi"])
        await asyncio.sleep(30.0)
    finally:
        await ctl.stop()

asyncio.run(main())