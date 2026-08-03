# Desktop companion stabilization: draggable Sprite2D, durable replies, bottom input, voice and structured cues

## Target release

`v1.1.0`

## Problem

The first native Sprite2D test exposes several connected usability and wiring
gaps:

1. The transparent avatar cannot be moved.
2. Text can be entered only in the separate panel, not below the avatar.
3. Completed replies disappear before a comfortable reading interval.
4. The avatar is not reliably kept above newly opened windows.
5. Runtime swap returns `unknown runtime ... expected one of []`.
6. LLM replies do not provide a validated emotion/action cue to the avatar.
7. There is no ready Windows profile for OpenRouter plus free local STT/TTS.
8. Live-wake and agent-voice controls change UI state without completing the
   expected speech-to-chat and TTS behavior; mock mode is not explained.
9. The empty task section does not explain whether anything should be running
   or which messages create tasks.

## Root causes

- Tauri click-through is whole-window; the original single transparent window
  cannot remain click-through over the PNG while also exposing a draggable,
  clickable region.
- The overlay route contains no input and window/theme YAML is not connected to
  the backend/frontend/Tauri shell.
- The bubble is cleared on a listening directive instead of using reply reading
  time.
- Initial avatar state is broadcast before late WebSocket clients connect.
- `Wiring.runtime_factories` is never populated and pack swap reads a stale
  runtime reference.
- The chat path treats the entire LLM response as display/TTS text and has no
  safe cue envelope.
- Profile loading, optional voice/LiteLLM installation, and a safe default
  `config/app.yaml` are incomplete.
- `agent_voice` is not consulted on later turns, speech finals are not submitted
  to chat, and Tauri PTT events are not forwarded to the backend.

## Scope

### Desktop and appearance

- Add an `avatar-controls` Tauri window below the transparent avatar.
- Keep the avatar click-through; keep the control strip interactive.
- Dragging the strip moves the avatar and persists its position.
- Render a compact text field in the strip.
- Reassert always-on-top for avatar and controls.
- Load validated public appearance settings from `config/theme.yml` through
  `GET /appearance`; apply window dimensions, scale, colors, visibility, gap,
  and bubble timing.

### Bubble and WebSocket state

- Do not clear a completed reply merely because listening starts.
- Hide it after `min(max_ms, base_ms + characters * ms_per_character)`.
- Cache/replay the latest avatar directive and completed bubble to late windows.

### Avatar cues

- Add the additive `AvatarCue` runtime event.
- Use the allow-listed JSON envelope configured by `config/personality.yml`.
- Strip the envelope before bubble/TTS output.
- Fall back safely for plain text, malformed JSON, or unknown values.
- Map emotion/action to visible Sprite2D states and retain gestures for richer
  runtimes.

### Voice

- Add `openrouter-voice` profile: LiteLLM/OpenRouter, local RealtimeSTT, local
  system TTS.
- Install optional dependencies when that profile is selected.
- Add a Windows launcher that loads `.env` without committing the API key.
- Make agent voice gate future TTS and interrupt current speech when disabled.
- Feed live-wake/PTT final transcripts into chat.
- Forward Tauri `Ctrl+Space` PTT events to WebSocket.
- Report real versus mock adapters in the panel.

### Tasks and runtime switching

- Explain that task cards are on-demand and list delegation examples.
- Wire task cancellation from WebSocket to `TaskRouter`.
- Register runtime factories and use the orchestrator's current runtime for pack
  swap.

## Acceptance criteria

- [ ] Avatar PNG background stays transparent.
- [ ] A visible strip below the avatar accepts clicks, text, and dragging.
- [ ] Dragging moves both windows and the position survives restart.
- [ ] Avatar and strip remain above normal newly opened windows.
- [ ] `config/theme.yml` changes are applied after restart.
- [ ] Completed reply timing follows the configured formula and is scrollable.
- [ ] A newly opened overlay receives current avatar and completed reply state.
- [ ] Sprite2D runtime swap no longer returns an empty expected-runtime list.
- [ ] Structured happy/wave and error/worried replies produce visible reactions.
- [ ] Plain-text LLM replies still work and raw JSON is not spoken or shown.
- [ ] OpenRouter key remains environment-only.
- [ ] Local STT/TTS profile reports real adapters and produces input/output.
- [ ] Agent voice off suppresses later TTS; live-wake/PTT transcripts trigger
      replies.
- [ ] Idle task panel explains that no background task is expected.
- [ ] Python tests, frontend tests/typecheck/build, and pack validation pass.

## Test evidence for the prepared v1.1.0 patch

- Full Python suite: passed (contract tests requiring installed entry-point
  distributions remain skipped in the source-only test environment).
- Frontend: 15 files / 86 tests passed.
- TypeScript typecheck and Vite production build: passed.
- `characters/octomimic` pack validation: passed.
- Backend smoke: `/health`, `/appearance`, `/chat`, and Sprite2D runtime swap
  returned successfully.
- Native Tauri/Rust compile: pending on a Windows/Rust-equipped runner; the
  source-only preparation environment did not provide `cargo` or `rustfmt`.

## Branch and merge workflow

Use the existing `dev` branch as the integration branch. If it already exists:

```bash
git fetch origin
git switch dev
git pull --ff-only origin dev
git switch -c feat/issue-<NUMBER>-desktop-stabilization-v1.1.0
```

If `dev` does not exist yet:

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c dev
git push -u origin dev
git switch -c feat/issue-<NUMBER>-desktop-stabilization-v1.1.0
```

Apply the versioned patch/source ZIP on the task branch, then:

```bash
git add -A
git commit -m "feat(desktop): stabilize overlay voice and avatar cues for v1.1.0"
git push -u origin feat/issue-<NUMBER>-desktop-stabilization-v1.1.0
```

Open a pull request from the task branch into `dev`. After approval, merge with
a merge commit and verify the integration branch:

```bash
git switch dev
git pull --ff-only origin dev
git merge --no-ff feat/issue-<NUMBER>-desktop-stabilization-v1.1.0
git push origin dev
```

Create the release tag only after the later `dev` to `main` release PR passes:

```bash
git switch main
git pull --ff-only origin main
git tag -a v1.1.0 -m "OpenMimicry v1.1.0"
git push origin v1.1.0
```
