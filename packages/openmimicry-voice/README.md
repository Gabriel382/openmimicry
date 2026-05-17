# openmimicry-voice

STT/TTS adapters and the `SpeechController` for OpenMimicry.

Ships:

- `MockSTTAdapter` / `MockTTSAdapter` — programmable, deterministic mocks.
- `RealtimeSTTAdapter` — wraps `RealtimeSTT.AudioToTextRecorder` (lazy-imported).
- `RealtimeTTSAdapter` — wraps `RealtimeTTS.TextToAudioStream` (lazy-imported).
- `SpeechController` — owns the single active TTS task, the barge-in policy, and the PTT / live-wake state machine.
- `WakeController` — thin enable/disable wrapper for callers that don't want the full SpeechController.

## Install

```bash
# Just the mocks + controllers (no audio device touched).
pip install openmimicry-voice

# Plus a real STT or TTS provider.
pip install "openmimicry-voice[realtimestt]"
pip install "openmimicry-voice[realtimetts]"
pip install "openmimicry-voice[voice]"           # both
```

## Usage

```python
import asyncio
from openmimicry.core import EventBus
from openmimicry.voice import MockSTTAdapter, MockTTSAdapter, SpeechController

async def main():
    bus = EventBus()
    stt = MockSTTAdapter()
    tts = MockTTSAdapter()
    ctl = SpeechController(stt=stt, tts=tts, bus=bus)
    await ctl.start()

    # Synthesise speech (barge-in enabled).
    await ctl.say("Hello world.")
    # ... TTSStarted, TTSFinished published on the bus ...

    # Push-to-talk:
    await ctl.ptt_down()
    await stt.push_transcript("hello", is_final=True)
    await ctl.ptt_up()
    # ... UserSpeechStarted, UserSpeechFinal published on the bus ...

    await ctl.stop()

asyncio.run(main())
```

## Invariants (from `docs/voice_modes.md`)

1. `SpeechController` is the **only** code that calls `tts.stop()`.
2. At most one TTS task is alive at any moment. `say()` cancels the previous before starting the next.
3. Barge-in waits `voice.modes.barge_in_grace_ms` before cancelling TTS, then re-checks `stt.vad_active`.

## See also

- [`docs/contracts.md`](../../docs/contracts.md) §4 — frozen `STTAdapter` / `TTSAdapter` / `SpeechController` / `WakeController`.
- [`docs/modules/M2_voice.md`](../../docs/modules/M2_voice.md) — module brief.
- [`docs/voice_modes.md`](../../docs/voice_modes.md) — PTT, wake-name, barge-in policy.
