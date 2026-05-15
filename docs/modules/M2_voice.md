# Module M2: `openmimicry-voice`

## Goal (1 line)

Ship the `RealtimeSTTAdapter`, `RealtimeTTSAdapter`, `SpeechController`, and `WakeController` implementations (plus mocks) so the backend can route push-to-talk, wake-name live mode, and interruptible TTS through a single controller.

## Scope and non-scope

**In scope.**

- `RealtimeSTTAdapter` wrapping `RealtimeSTT.AudioToTextRecorder`.
- `RealtimeTTSAdapter` wrapping `RealtimeTTS.TextToAudioStream`.
- `SpeechController` concrete implementation owning the single active TTS task and barge-in policy.
- `WakeController` concrete implementation.
- `MockSTTAdapter`, `MockTTSAdapter` — canonical fixtures consumed by every other module.

**Non-scope.**

- The Protocols (Phase 0).
- The actual audio device — RealtimeSTT/TTS handle that. We do not implement audio I/O.
- LLM integration (M1 + M6).
- The frontend audio meter (M7).

## Inputs (immutable, from contracts.md)

- `STTAdapter`, `TTSAdapter`, `SpeechController`, `WakeController` Protocols (`contracts.md` §4).
- Schemas: `STTConfig`, `TTSConfig`, `Transcript`, `WakeEvent`, `TTSChunkBoundary` (`contracts.md` §4).
- `RuntimeEvent` variants this module publishes: `UserSpeechStarted`, `UserSpeechFinal`, `TranscriptPreview`, `WakeDetected`, `TTSStarted`, `TTSChunkSpoken`, `TTSFinished`, `TTSInterrupted`, `ErrorEvent` (`contracts.md` §2.1).
- `VoiceConfig` sub-config from `AppConfig.voice` ([`../configuration.md`](../configuration.md)).
- `EventBus` from `openmimicry.core` (M0).

## Outputs (this module owns)

```text
packages/openmimicry-voice/
  pyproject.toml
  README.md
  src/openmimicry/voice/
    __init__.py
    stt/
      __init__.py
      base.py             # re-export of STTAdapter
      realtimestt_adapter.py
    tts/
      __init__.py
      base.py             # re-export of TTSAdapter
      realtimetts_adapter.py
    controllers/
      __init__.py
      speech.py           # SpeechController concrete
      wake.py             # WakeController concrete
    mocks.py              # MockSTTAdapter, MockTTSAdapter
tests/unit/voice/
  test_mock_stt.py
  test_mock_tts.py
  test_speech_controller.py
  test_wake_controller.py
  test_realtimestt_adapter.py    # heavily mocked
  test_realtimetts_adapter.py    # heavily mocked
tests/contract/test_stt.py        # un-skipped
tests/contract/test_tts.py        # un-skipped
tests/contract/test_speech_controller.py
```

Optional deps in `pyproject.toml`:
- `[realtimestt]`: `RealtimeSTT>=0.3`
- `[realtimetts]`: `RealtimeTTS>=0.4`
- `[voice]`: both of the above

## Mock implementations this module provides

```python
# openmimicry.voice.mocks
class MockSTTAdapter:
    name: str = "mock-stt"

    def __init__(self) -> None: ...

    # Test helpers (not part of the Protocol):
    async def push_transcript(self, text: str, is_final: bool = True) -> None:
        """Queue a Transcript onto the async stream."""
    async def trigger_speech_start(self) -> None:
        """Set vad_active=True."""
    async def trigger_speech_end(self) -> None:
        """Set vad_active=False."""

class MockTTSAdapter:
    name: str = "mock-tts"
    spoken: list[str]       # everything passed to speak()
    interrupt_calls: int

    def __init__(self, *, chunk_interval_s: float = 0.01) -> None: ...
```

`MockSTTAdapter` is fully programmable. M6's integration tests drive `push_transcript(...)` and assert on bus events.

## Test surface

- **Contract.** `tests/contract/test_stt.py` parametrises over `MockSTTAdapter`, `RealtimeSTTAdapter` (skipif). Asserts `start(config)` opens, `transcripts` yields, `stop()` closes, `vad_active` toggles, `healthcheck` returns bool.
- **Contract.** `tests/contract/test_tts.py` parametrises over `MockTTSAdapter`, `RealtimeTTSAdapter` (skipif). Asserts `speak("hi", config=...)` completes, `stop()` cancels within 100ms, `is_speaking` toggles.
- **Contract.** `tests/contract/test_speech_controller.py` exercises the controller against the two mock adapters.
- **Unit.** `SpeechController.say()` cancels a previous `say()`. PTT-down cancels TTS. Barge-in respects `barge_in_grace_ms`. Wake disables/enables correctly.
- **Unit.** `RealtimeSTTAdapter` translates RealtimeSTT callbacks to the async `transcripts` stream via an internal `asyncio.Queue` (mock the underlying library).

## Step-by-step plan (atomic, numbered)

1. Create `packages/openmimicry-voice/pyproject.toml`. Optional deps `[realtimestt]`, `[realtimetts]`, `[voice]`.
2. Replace Phase 0 stub `mocks.py`:
   - `MockSTTAdapter`: holds `asyncio.Queue[Transcript]`. `transcripts` returns an async iterator draining the queue. `start()` records the config. `push_transcript`, `trigger_speech_start`, `trigger_speech_end` are test helpers.
   - `MockTTSAdapter`: `speak()` sleeps `chunk_interval_s` per logical chunk and checks a cancel flag. Records every `text` into `spoken`. `stop()` flips the cancel flag.
3. Implement `stt/realtimestt_adapter.py`. Lazy-import `RealtimeSTT`. Constructor stores config. `start()` constructs `AudioToTextRecorder(on_realtime_transcription_update=..., on_recording_start=..., ...)` and registers callbacks that push into an `asyncio.Queue`. `stop()` calls `recorder.stop()` and closes the queue.
4. Implement `tts/realtimetts_adapter.py`. Lazy-import `RealtimeTTS`. Construct `TextToAudioStream(<engine>)` based on `TTSConfig.engine` (factory mapping for `coqui`, `piper`, `azure`, etc.). `speak(text_or_stream)` accepts either a string or an async iterable of strings; in the stream case, push tokens with `stream.feed(...)` and `stream.play_async(...)`. Implement a cooperative cancel flag.
5. Implement `controllers/speech.py::SpeechController`:
   - Holds `stt`, `tts`, `bus`, `cfg: VoiceConfig`, `_current_tts_task: asyncio.Task | None`, `_vad_grace_task: asyncio.Task | None`.
   - `say()` cancels `_current_tts_task` first, then starts a new one. Publishes `TTSStarted` → tts.speak → `TTSFinished` (or `TTSInterrupted` on cancel).
   - `ptt_down()` cancels TTS, then `stt.start(STTConfig(mode="dictation"))`, publishes `UserSpeechStarted`.
   - `ptt_up()` awaits the final transcript, publishes `UserSpeechFinal`, `stt.stop()`.
   - `enable_live_listening(wake_names)` runs `stt.start(STTConfig(mode="wake", wake_names=...))`. Subscribes to the transcripts stream; on a wake event, switches to `dictation` mode (this is the wake → dictation transition described in `event_flows.md`).
   - Barge-in: a background task watches `stt.vad_active`; if true while `tts.is_speaking`, awaits `barge_in_grace_ms`, re-checks, and on persisting activity calls `interrupt()`.
6. Implement `controllers/wake.py::WakeController`. Thin wrapper around STT; `enable()` calls `stt.start(STTConfig(mode="wake", ...))`. May be merged into SpeechController if simpler.
7. Write the unit tests. For barge-in, use `pytest.mark.asyncio` and a `MockSTTAdapter` that triggers VAD followed by a short delay; assert `TTSInterrupted` is published.
8. Un-skip the contract tests.
9. Register `MockSTTAdapter`, `RealtimeSTTAdapter`, `MockTTSAdapter`, `RealtimeTTSAdapter` via entry points (`openmimicry.contracts.stt`, `openmimicry.contracts.tts`).
10. Write `packages/openmimicry-voice/README.md` with a 15-line usage example wiring a `SpeechController` and pushing a fake transcript.
11. Update `CHANGELOG.md`.
12. `make ci`. Open PR `feat(voice): M2 — RealtimeSTT/RealtimeTTS adapters + SpeechController`.

## Definition of done (checklist)

- [ ] `MockSTTAdapter`, `MockTTSAdapter` are usable by other modules and pass the contract test.
- [ ] `RealtimeSTTAdapter` and `RealtimeTTSAdapter` import cleanly when their extras are installed; raise an actionable error otherwise.
- [ ] `SpeechController.say()` cancels the previous utterance and publishes `TTSInterrupted` when cancelled.
- [ ] PTT-down cancels TTS within 100 ms (timed assertion in a unit test using `MockTTSAdapter`).
- [ ] Barge-in honours `voice.modes.barge_in_grace_ms`.
- [ ] Live wake → dictation → wake cycle is testable end-to-end against `MockSTTAdapter.push_transcript(...)`.
- [ ] Contract tests pass; coverage ≥ 80%.
- [ ] `scripts/check_imports.py` clean.
- [ ] `CHANGELOG.md` entry.

## Recommended LLM brief (copy-pasteable prompt)

> You are implementing **Module M2 (`openmimicry-voice`)** of OpenMimicry. The Protocols and schemas are frozen.
>
> Read in order:
>
> 1. `docs/contracts.md` §4 — `STTAdapter`, `TTSAdapter`, `SpeechController`, `WakeController` Protocols and their schemas.
> 2. `docs/modules/M2_voice.md` — this brief.
> 3. `docs/voice_modes.md` — barge-in policy, mode toggles, the interruptible-TTS invariants.
> 4. `docs/event_flows.md` §2 and §3 — exact PTT and wake-name event sequences you must reproduce.
> 5. RealtimeSTT docs: https://github.com/KoljaB/RealtimeSTT
> 6. RealtimeTTS docs: https://github.com/KoljaB/RealtimeTTS
>
> Implement the 12-step plan. Critical invariants from `voice_modes.md`:
>
> - `SpeechController` is the **only** code that calls `tts.stop()`. The avatar director does not. The LLM does not.
> - At most one TTS task is alive at any moment. `say()` cancels the previous before starting the next.
> - Barge-in waits `voice.modes.barge_in_grace_ms` before cancelling TTS, then re-checks VAD.
>
> Ship `MockSTTAdapter` and `MockTTSAdapter` with the test helpers documented in the brief. Other modules (M6 backend, integration tests) depend on those helpers being present and stable. Register all four classes via entry points.
>
> Constraint: do not import from `openmimicry-llm`, `openmimicry-avatar`, `openmimicry-tasks`. Only `openmimicry-core`. Open the PR titled `feat(voice): M2 — RealtimeSTT/RealtimeTTS adapters + SpeechController` with the Definition-of-done checklist ticked.
