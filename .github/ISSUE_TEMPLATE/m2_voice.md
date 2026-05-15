---
name: "M2: openmimicry-voice"
about: RealtimeSTTAdapter, RealtimeTTSAdapter, SpeechController, WakeController
title: "[M2] openmimicry-voice — RealtimeSTT/RealtimeTTS + SpeechController"
labels: ["module", "M2", "voice"]
assignees: []
---

## Overview

Ship the voice adapter family and the controller that enforces interruptible-TTS and barge-in invariants.

**Parallelism: parallel with M1, M3, M5, M7.** Depends on Phase 0 and M0.

## Required reading

1. [`docs/contracts.md`](../docs/contracts.md) §4
2. [`docs/modules/M2_voice.md`](../docs/modules/M2_voice.md)
3. [`docs/voice_modes.md`](../docs/voice_modes.md)
4. [`docs/event_flows.md`](../docs/event_flows.md) §2 and §3
5. [RealtimeSTT](https://github.com/KoljaB/RealtimeSTT) / [RealtimeTTS](https://github.com/KoljaB/RealtimeTTS)

## LLM brief

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

## Definition of done

See [`docs/modules/M2_voice.md`](../docs/modules/M2_voice.md).
