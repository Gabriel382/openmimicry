# openmimicry-voice

STT/TTS adapters and the `SpeechController` for OpenMimicry.

Ships:

- `MockSTTAdapter` / `MockTTSAdapter` — programmable, deterministic mocks.
- `IsolatedFasterWhisperAdapter` — supervises a preloaded microphone/model child service.
- `IsolatedPiperTTSAdapter` — runs every synthesis/playback in a disposable process.
- `RealtimeSTTAdapter` / `RealtimeTTSAdapter` — compatibility adapters, not the supported Windows default.
- `SpeechController` — owns the single active TTS task, the barge-in policy, and the PTT / continuous-listening / wake-name state machine.
- `WakeController` — thin enable/disable wrapper for callers that don't want the full SpeechController.

## Install

```bash
# From this repository on Windows: install the complete tested voice profile.
.\scripts\win\install.bat openrouter-voice

# Package-development equivalent, using this checkout rather than a registry release.
python -m pip install -e "packages/openmimicry-voice[voice]"
```

The Windows profile installs Faster-Whisper, Piper, NumPy, and SoundDevice into
the repository `.venv`. The launcher downloads the free
`en_US-lessac-medium` voice and runs `scripts/voice_doctor.py` before enabling
voice. Legacy realtime dependencies are available separately with
`openmimicry-voice[legacy-realtime]`.

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

    # Queue speech. TTSStarted is published only after playback starts.
    await ctl.say("Hello world.")
    # ... TTSStarted, TTSFinished published on the bus ...

    # Push-to-talk:
    await ctl.ptt_down()
    await stt.push_transcript("hello", is_final=True)
    await ctl.ptt_up()
    # ... UserSpeechStarted, UserSpeechFinal published on the bus ...

    # Or listen hands-free, accepting only name-prefixed commands:
    await ctl.enable_live_listening(wake_names=["Mimi", "Hey Mimi"])
    await stt.push_transcript("Mimi, hands-free hello", is_final=True)
    # Publishes UserSpeechFinal(text="hands-free hello", ...)
    await ctl.disable_live_listening()

    await ctl.stop()

asyncio.run(main())
```

## Invariants (from `docs/voice_modes.md`)

1. `SpeechController` is the **only** code that calls `tts.stop()`.
2. At most one TTS task is alive at any moment. `say()` cancels the previous before starting the next.
3. Text delivery never waits for TTS readiness.
4. Barge-in waits `voice.modes.barge_in_grace_ms` before cancelling TTS, then re-checks `stt.vad_active`.

## See also

- [`docs/contracts.md`](../../docs/contracts.md) §4 — frozen `STTAdapter` / `TTSAdapter` / `SpeechController` / `WakeController`.
- [`docs/modules/M2_voice.md`](../../docs/modules/M2_voice.md) — module brief.
- [`docs/voice_modes.md`](../../docs/voice_modes.md) — PTT, continuous listening, wake-name, and barge-in policy.
