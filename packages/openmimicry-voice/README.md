# openmimicry-voice

STT/TTS adapters and the `SpeechController` for OpenMimicry.

Ships:

- `MockSTTAdapter` / `MockTTSAdapter` — programmable, deterministic mocks.
- `RealtimeSTTAdapter` — wraps `RealtimeSTT.AudioToTextRecorder` (lazy-imported).
- `RealtimeTTSAdapter` — wraps `RealtimeTTS.TextToAudioStream` (lazy-imported).
- `SpeechController` — owns the single active TTS task, the barge-in policy, and the PTT / continuous-listening / wake-name state machine.
- `WakeController` — thin enable/disable wrapper for callers that don't want the full SpeechController.

## Install

```bash
# From this repository on Windows: install the complete tested voice profile.
.\scripts\win\install.bat openrouter-voice

# Package-development equivalent, using this checkout rather than a registry release.
python -m pip install -e "packages/openmimicry-voice[voice]"
```

The Windows profile installs `RealtimeSTT[faster-whisper]` and
`RealtimeTTS[system]` into the repository's `.venv`. The launcher checks the
concrete recorder, stream, and system-engine imports before it starts, so a
different global Python installation—or an engine-less base distribution—
cannot accidentally look healthy. Python 3.13+ installs `audioop-lts`
automatically because the standard-library `audioop` module was removed in
that Python release while RealtimeTTS/pydub still imports its API.

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
3. Barge-in waits `voice.modes.barge_in_grace_ms` before cancelling TTS, then re-checks `stt.vad_active`.

## See also

- [`docs/contracts.md`](../../docs/contracts.md) §4 — frozen `STTAdapter` / `TTSAdapter` / `SpeechController` / `WakeController`.
- [`docs/modules/M2_voice.md`](../../docs/modules/M2_voice.md) — module brief.
- [`docs/voice_modes.md`](../../docs/voice_modes.md) — PTT, continuous listening, wake-name, and barge-in policy.
