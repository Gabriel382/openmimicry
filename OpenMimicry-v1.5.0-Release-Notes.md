# OpenMimicry v1.5.0 release notes

OpenMimicry v1.5.0 replaces the supported Windows voice path rather than adding
another recovery wrapper around RealtimeSTT/RealtimeTTS. The backend no longer
owns microphone, Whisper, COM, synthesis, or playback resources.

## User-visible changes

- Repeated voice replies use independent Piper processes. A broken playback can
  be terminated without affecting the next response.
- Faster-Whisper runs in a supervised, preloaded service process. PTT release
  finalizes one recording; wake/continuous modes finalize every VAD utterance.
- `medium.en` is the stronger CPU default. `distil-large-v3`, `large-v3`, and
  lower-resource options are available in the dashboard.
- Assistant text is displayed as soon as the LLM completes. Audio cannot hide
  an OpenRouter response or block another message.
- Speaking animation begins only when playback begins. Listening has priority
  over stale output state.
- The Windows launcher downloads the free Piper voice and runs a multi-turn
  hardware/model preflight before starting the verified runtime.

## Compatibility

Configuration schema version remains 1; the change is additive. Existing
`realtimestt` and `realtimetts` adapter names remain valid when the
`legacy-realtime` extra is installed, but the shipped OpenRouter voice profile
uses `isolated-faster-whisper` and `isolated-piper`.

Changing voice adapters requires a backend restart. Wake names, model selection,
endpointing pause, agent voice, and listening modes remain dashboard-controlled.

## Verification

The Python suite covers two consecutive STT turns, two consecutive TTS turns,
and recovery after killing a hung TTS process. The Windows release gate is
documented in `docs/V1.5.0_WINDOWS_TESTING.md`.
