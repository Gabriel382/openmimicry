# v1.5.0 — replace the Windows voice lifecycle with isolated finite jobs

## Problem

RealtimeTTS/SystemEngine reliably spoke the first reply but could stall after
`stream start` on later replies, including after a clean first completion.
RealtimeSTT also exposed invalid-handle and long-lived recorder failures. The
application incorrectly delayed LLM text behind TTS readiness, making healthy
OpenRouter replies appear missing and allowing stale speaking state to replace
listening.

## Scope

- [x] Add a preloaded Faster-Whisper child service for finite microphone turns.
- [x] Add disposable Piper synthesis/playback jobs with bounded termination.
- [x] Make text/history delivery independent of TTS readiness.
- [x] Publish speaking only after playback starts.
- [x] Raise the CPU default to `medium.en` and expose stronger GPU options.
- [x] Add a Windows dependency/device/model preflight.
- [x] Retain Realtime adapters only as explicit legacy options.
- [x] Add repeat-turn and forced-hang process-boundary regressions.
- [ ] Complete the real Windows matrix in `docs/V1.5.0_WINDOWS_TESTING.md`.

## Branch and merge workflow

```bash
git switch dev
git pull --ff-only
git switch -c feat/v1.5.0-isolated-voice-runtime
```

After review and the Windows matrix:

```bash
git switch dev
git merge --no-ff feat/v1.5.0-isolated-voice-runtime
git tag -a v1.5.0 -m "OpenMimicry v1.5.0"
git push origin dev v1.5.0
```

Versioning rationale: this is a minor release because it adds supported adapter
names, runtime processes, configuration fields, model choices, and a preflight
workflow while keeping schema version 1 and existing adapter names valid.
