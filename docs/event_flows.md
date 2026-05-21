# Event flows

This document specifies the four canonical event flows in OpenMimicry. Each flow is described as a sequence of events on the in-process bus, with the producing module on the left and the resulting `AvatarDirective`s on the right. All flows assume the runtime is built and the WebSocket projection to the frontend is open.

Legend:

- `[FE]` frontend (React, in the overlay/panel window) — only for *non-avatar* projection (text bubble, task cards, system notices)
- `[BE]` backend (FastAPI process)
- `[CORE]` `openmimicry-core` (bus, runtime)
- `[LLM]` `openmimicry-llm`
- `[VC]` `openmimicry-voice` SpeechController
- `[STT]` `openmimicry-voice` STT adapter
- `[TTS]` `openmimicry-voice` TTS adapter
- `[AV]` `openmimicry-avatar` AvatarDirector
- `[AR]` `openmimicry-avatar` chosen `AvatarRuntimeAdapter` (Sprite2D, Three.js, Unity, …) — receives `AvatarDirective` via `AvatarOrchestrator`
- `[TK]` `openmimicry-tasks` router/adapter
- `pub:` publish to bus
- `→AR:` directive handed to the active `AvatarRuntimeAdapter`
- `→FE:` projected to the frontend via WebSocket (non-avatar channels)

## 1. Text input

```text
[FE]  user types in panel, presses Enter
[FE]  WS send: {type: "user_text", text: "Summarise this PDF."}
[BE]  validates, calls Runtime.handle_user_text(text)
[CORE]pub: UserTextSubmitted(text)
[AV]  on(UserTextSubmitted) -> AvatarDirective(thinking)
[AV]  emits AvatarDirective(state=thinking)
[CORE]→AR: orchestrator.apply_directive(...)    (Sprite2D / ThreeJS / Unity / …)
[LLM] LLMRouter.generate(messages) starts streaming
[LLM] pub: LLMTokenStreamed(delta="Sure, ")
[LLM] pub: LLMTokenStreamed(delta="here is ...")
                                                →FE: speech-bubble text grows
[VC]  if cfg.voice.modes.agent_voice == true:
        starts TTSAdapter.speak(<async stream of deltas>)
        pub: TTSStarted
[AV]  on(TTSStarted) -> AvatarDirective(speaking, speaking=true)
[AV]  emits AvatarDirective(state=speaking, speaking=true)
[CORE]→AR: orchestrator.apply_directive(...)
[TTS] periodic pub: TTSChunkSpoken              (heartbeat)
[LLM] pub: LLMReplyComplete(full_text)
[TTS] finishes draining buffered tokens
[VC]  pub: TTSFinished
[AV]  on(TTSFinished) -> AvatarDirective(idle)
[AV]  emits AvatarDirective(state=idle)
[CORE]→AR: orchestrator.apply_directive(...)
```

Cancellation: if the user submits a new message before the previous reply finishes, the runtime calls `SpeechController.interrupt()` (which calls `TTS.stop()` and cancels the LLM generator task), publishes `TTSInterrupted`, and starts over from `UserTextSubmitted`. The avatar passes through `idle` for a single tick before going `thinking` again, so the transition is visible.

## 2. Push-to-talk

```text
[FE]  global hotkey Ctrl+Space pressed
[FE]  WS send: {type: "ptt_down"}
[BE]  Runtime.ptt_down() -> SpeechController.ptt_down()
[VC]  cancels any active TTS (calls TTS.stop())
[VC]  STTAdapter.start(STTConfig(mode="dictation"))
[CORE]pub: UserSpeechStarted
[AV]  on(UserSpeechStarted) -> AvatarDirective(listening)
[AV]  emits AvatarDirective(state=listening)
[CORE]→AR: orchestrator.apply_directive(...)

  ... user speaks ...

[STT] pub: TranscriptPreview(text="summarise ...", is_final=False)
                                                →FE: render preview in bubble

[FE]  hotkey released
[FE]  WS send: {type: "ptt_up"}
[BE]  Runtime.ptt_up() -> SpeechController.ptt_up()
[VC]  STTAdapter.stop()
[STT] pub: UserSpeechFinal(text="summarise the PDF")
[VC]  ...flow joins Text input flow from `UserTextSubmitted`
```

Edge cases:

- Hotkey pressed while TTS is speaking: TTS is cancelled immediately (barge-in by intent).
- Hotkey held for <100ms: treated as a no-op (debounce in `SpeechController`).
- No speech detected during PTT window: publish `UserSpeechFinal(text="", reason="no_speech")` so the avatar returns to `idle` without invoking the LLM.

## 3. Wake-name live mode

```text
[BE]  on startup, if cfg.voice.modes.live_wake == true:
        SpeechController.enable_live_listening(wake_names=["Mimi"])
        WakeController.enable()
[VC]  STTAdapter.start(STTConfig(mode="wake", wake_names=[...]))

  ... silence ...
  ... user says "Mimi, summarise this." ...

[STT] internal wake-word fires
[WK]  pub: WakeDetected(name="Mimi")
[AV]  on(WakeDetected) -> AvatarDirective(listening)
[VC]  if TTS speaking: cancel + pub: TTSInterrupted   (barge-in)
[VC]  STT switches to STTConfig(mode="dictation")
[CORE]pub: UserSpeechStarted

  ... STT publishes TranscriptPreview frames ...
                                                →FE: render preview in bubble

[STT] silence threshold reached
[STT] pub: UserSpeechFinal(text="summarise this")
[VC]  STT returns to STTConfig(mode="wake")
[VC]  ...flow joins Text input flow
```

The wake -> dictation -> wake transitions are owned by `SpeechController`, not by the frontend. The frontend just sees `AvatarDirective` and `TranscriptPreview` events and renders them.

Barge-in semantics (when TTS is speaking and live wake is on):

- If `cfg.voice.tts.interruptible == true` and STT VAD reports voice activity, the controller calls `TTS.stop()` and emits `TTSInterrupted` even before the wake word is detected. The avatar transitions to `listening` immediately. If the user does not subsequently utter the wake name within `cfg.voice.modes.barge_in_grace_ms`, the system returns to `idle`.

## 4. Task delegation

Two entry points: an explicit user request ("send this to Claude Code") or an LLM tool call. Both end up creating a `TaskRequest`.

```text
[CORE]TaskRouter.submit(req) chooses adapter
[TK]  adapter.submit(req) -> TaskHandle(id="t_42")
[CORE]pub: TaskSubmitted(handle=t_42, summary="refactor utils.py")
[AV]  on(TaskSubmitted) -> AvatarDirective(thinking)   (or 'working' if pack defines it)

  ... adapter streams updates ...

[TK]  for u in adapter.updates(handle):
        pub: TaskUpdated(handle=t_42, status="running",
                         note="diffing 12 files", progress=0.4)
                                                       →FE: task card refreshes
[TK]  pub: TaskCompleted(handle=t_42, result=TaskResult(...))
[AV]  on(TaskCompleted) -> AvatarDirective(state=happy, next_state=idle,
                                             duration_ms=cfg.avatar.celebration_ms)
[CORE]→AR: orchestrator.apply_directive(...)
[CORE]→AR: orchestrator.apply_directive(state=idle)   (after duration_ms)
```

If the user asked vocally ("Ask Claude to refactor this file"), the LLM still runs first to produce a `TaskRequest`; only then does the router dispatch. The avatar therefore goes through `thinking -> (speaking if a confirmation is read aloud) -> thinking -> happy -> idle`.

Failure path: `TaskUpdated(status="failed", error=...)` -> `AvatarDirective(state=error, next_state=idle, duration_ms=cfg.avatar.error_ms)`.

## 5. Avatar runtime vs. frontend projection

There are two distinct outbound channels from the backend:

```text
AvatarDirective    -> AvatarRuntimeAdapter.apply_directive(...)
                      (Sprite2D, ThreeJS, Live3D, Unity, External, Mock)

Frontend projection over WebSocket (non-avatar UI):
  TranscriptPreview   when speech_controller has a live preview
  SpeechBubbleText    assembled from LLMTokenStreamed deltas
  TaskCardEvent       derived from TaskSubmitted/TaskUpdated/TaskCompleted
  SystemNotice        health, errors, mode changes, runtime swaps
```

Why split: the avatar channel is *modality-shaped* (the directive serializes differently for a Unity WS bridge than for the Sprite2D in-window renderer), and the frontend channel is UI-shaped. Mixing them would force every external renderer to also implement the panel UI projection. Keeping them separate is what makes Unity and external renderers trivial to write: they only care about `AvatarDirective`.

Everything else (raw `LLMTokenStreamed`, `TTSChunkSpoken` heartbeats, internal state) stays inside the backend. This keeps both consumers dumb and the surface area for breaking changes small.

## 6. Why this is testable

Every flow above is exercised in `tests/integration/test_flows.py` by:

1. Wiring `MockLLMAdapter`, `MockSTTAdapter`, `MockTTSAdapter` to the real `SpeechController`, `AvatarDirector`, and `EventBus`.
2. Driving the entry-point method (`handle_user_text`, `ptt_down/up`, `WakeDetected`, `TaskRouter.submit`).
3. Asserting on the ordered list of bus events the bus saw.

That gives us regression coverage for the contracts above without depending on a real model, mic, or speaker.
