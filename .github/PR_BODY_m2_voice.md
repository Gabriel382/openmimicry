# feat(voice): M2 — RealtimeSTT/RealtimeTTS adapters + SpeechController

Lands `openmimicry-voice` per `docs/modules/M2_voice.md`. M2 implements the frozen `STTAdapter`, `TTSAdapter`, `SpeechController`, and `WakeController` Protocols from `docs/contracts.md` §4, and ships the canonical mock adapters that every downstream module (M3 director tests, M6 backend, integration suite) depends on.

## Adapters

- **`MockSTTAdapter` / `MockTTSAdapter`** — replace the Phase 0 `NotImplementedError` stubs. Programmable, deterministic, no audio device touched. `MockSTTAdapter.push_transcript(text, is_final=...)` drives the async stream; `trigger_speech_start/end` toggle `vad_active` for barge-in tests. `MockTTSAdapter.speak()` records every text into `spoken` and honours a cooperative cancel flag (`stop()`).
- **`RealtimeSTTAdapter`** — wraps `RealtimeSTT.AudioToTextRecorder`. **Lazy-imports** `RealtimeSTT` inside `start()`/`healthcheck()` so a mocks-only install needs none of it. Translates RealtimeSTT's thread-callback model into the async `transcripts` stream via `loop.call_soon_threadsafe` + `asyncio.Queue`. Maps `STTConfig.vad`/`wake_names`/`mode` onto the recorder's constructor kwargs. Raises a typed `RealtimeSTTUnavailable` if the extra isn't installed.
- **`RealtimeTTSAdapter`** — wraps `RealtimeTTS.TextToAudioStream`. Lazy-imports; engine selection (`coqui` / `piper` / `azure` / `openai` / `system` fallback) is centralised in `_build_engine()` so M6 can monkey-patch it. Cooperative cancel via `_cancel` Event polled against `stream.is_playing()`. Typed `RealtimeTTSUnavailable`.

## Controllers

- **`SpeechController`** — the heart of M2. Owns the single in-flight TTS task and is **the only code that calls `tts.stop()`**.
  - `say()` calls `interrupt()` first → at most one TTS task alive at any moment. Publishes `TTSStarted`, then `TTSFinished` (or `TTSInterrupted` on cancel).
  - `ptt_down()` cancels TTS, opens STT in `mode="dictation"`, publishes `UserSpeechStarted`.
  - `ptt_up()` awaits the next final transcript (2-second timeout), publishes `UserSpeechFinal(reason="normal"|"no_speech")`.
  - `enable_live_listening(wake_names=...)` starts STT in `mode="wake"` and backgrounds a projector task that publishes `TranscriptPreview` for partials and `UserSpeechFinal` for finals.
  - Barge-in: a background task polls `stt.vad_active` at `barge_in_grace_ms / 4` cadence. If VAD persists across the grace window while TTS is playing, the task calls `interrupt()`. `voice.tts.interruptible=false` disables it.
- **`WakeController`** — thin wrapper around an STT in `mode="wake"`. Exists for callers (e.g. Tauri tray-menu toggle) that don't want the full SpeechController.

## Entry-point registration

```toml
[project.entry-points."openmimicry.contracts.stt"]
mock = "openmimicry.voice.mocks:make_mock_stt_adapter"
realtimestt = "openmimicry.voice.stt.realtimestt_adapter:make_realtimestt_adapter"

[project.entry-points."openmimicry.contracts.tts"]
mock = "openmimicry.voice.mocks:make_mock_tts_adapter"
realtimetts = "openmimicry.voice.tts.realtimetts_adapter:make_realtimetts_adapter"

[project.entry-points."openmimicry.contracts.speech_controller"]
default = "openmimicry.voice.controllers.speech:make_speech_controller"
```

The Phase 0 contract conftest picks them up automatically.

## Optional installs

```bash
pip install "openmimicry-voice[realtimestt]"   # microphone STT
pip install "openmimicry-voice[realtimetts]"   # speaker TTS
pip install "openmimicry-voice[voice]"         # both
```

## Tests

- **`tests/unit/voice/`** — 25+ new unit tests:
  - `test_mock_stt.py`, `test_mock_tts.py` — Protocol-isinstance, helpers, `<100ms` stop assertion.
  - `test_speech_controller.py` — `say()` lifecycle, `say()` cancels previous & publishes `TTSInterrupted`, `ptt_down` cancels TTS in `<100ms`, `ptt_up` publishes `UserSpeechFinal`, barge-in fires within the grace window, live-listening starts STT in wake mode.
  - `test_wake_controller.py` — enable/disable idempotency.
  - `test_realtimestt_adapter.py`, `test_realtimetts_adapter.py` — inject fake `RealtimeSTT`/`RealtimeTTS` modules via `sys.modules` so CI stays hermetic. Cover partial-transcript callback streaming, VAD tracking, wake-word translation, stop cancellation, async-stream input.
- **`tests/contract/test_stt.py`**, **`test_tts.py`**, **`test_speech_controller.py`** — un-skipped. Hermetic checks call into the mocks; Realtime adapters are skipped via a `name == "mock-*"` guard so the contract suite never touches real hardware.

## Smoke demo

`scripts/m2_demo.py` plus two `Makefile` targets so reviewers can verify behaviour in one command:

```bash
make m2-demo                           # say() + PTT + live-wake, prints every RuntimeEvent
make m2-demo-barge-in                  # exercises the barge-in path
```

## Definition-of-done checklist

- [x] `MockSTTAdapter`, `MockTTSAdapter` are usable by other modules and pass the contract test.
- [x] `RealtimeSTTAdapter` / `RealtimeTTSAdapter` import cleanly when their extras are installed; raise `RealtimeSTTUnavailable` / `RealtimeTTSUnavailable` with an actionable message otherwise.
- [x] `SpeechController.say()` cancels the previous utterance and publishes `TTSInterrupted` when cancelled.
- [x] PTT-down cancels TTS within 100 ms (timed assertion in `test_mock_tts.py::test_stop_cancels_speak_within_100ms` and `test_speech_controller.py::test_ptt_down_cancels_tts_within_100ms`).
- [x] Barge-in honours `voice.modes.barge_in_grace_ms` (timed assertion in `test_speech_controller.py::test_barge_in_interrupts_when_vad_active`).
- [x] Live wake → dictation → wake cycle is testable end-to-end against `MockSTTAdapter.push_transcript(...)`.
- [x] Contract tests pass.
- [x] `scripts/check_imports.py` clean — `openmimicry-voice` depends only on `openmimicry-core`.
- [x] `CHANGELOG.md` entry added.

## Files

24 new / replaced files, ~1.2 k LOC.

```
packages/openmimicry-voice/
  pyproject.toml                                     [extras + 3 entry-point groups]
  README.md                                          [usage + invariants]
  src/openmimicry/voice/__init__.py                  [re-exports]
  src/openmimicry/voice/py.typed
  src/openmimicry/voice/mocks.py                     [replaces Phase 0 stub]
  src/openmimicry/voice/stt/{__init__,base,realtimestt_adapter}.py
  src/openmimicry/voice/tts/{__init__,base,realtimetts_adapter}.py
  src/openmimicry/voice/controllers/{__init__,speech,wake}.py
tests/unit/voice/
  __init__.py
  test_mock_stt.py, test_mock_tts.py
  test_speech_controller.py, test_wake_controller.py
  test_realtimestt_adapter.py, test_realtimetts_adapter.py
tests/contract/
  test_stt.py, test_tts.py, test_speech_controller.py    [un-skipped]
scripts/m2_demo.py                                       [interactive smoke]
Makefile                                                  [+ m2-demo, m2-demo-barge-in]
CHANGELOG.md                                              [M2 entry]
```

## Labels

`module:voice`, `m2`
