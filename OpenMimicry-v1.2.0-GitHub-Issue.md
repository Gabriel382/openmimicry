# Replace the native side panel with an avatar toolbar and reliable voice input

## Target release

`v1.2.0`

## Problem

The v1.1 desktop is usable, but its interaction model still feels split across
two separate products. The native side panel duplicates controls that belong
next to the avatar, the drag strip is below the character, and the label
“Live wake” does not explain whether it waits for a name or ordinary speech.
Real voice also fails unclearly when `RealtimeSTT` or `RealtimeTTS` was installed
outside the repository's active virtual environment.

## Scope

- Dock the interactive toolbar above the transparent avatar.
- Keep drag, a literal lock/unlock control, hold-to-talk, Auto listen, agent
  voice, settings, and exit on that toolbar.
- Persist the position-lock state and prevent movement while locked.
- Remove the native side-panel window.
- Open settings, diagnostics, chat, and task cards at the backend's local
  `/dashboard` route in the default browser.
- Support two unambiguous microphone paths:
  - PTT while the toolbar microphone or `Ctrl+Space` is held.
  - VAD-driven continuous listening without a wake phrase.
- Pause continuous listening during PTT and restore it afterward so only one
  consumer reads the STT stream.
- Keep legacy wake-name mode available through `live_wake`, but do not expose it
  as the normal hands-free toolbar action.
- Verify voice dependencies in `.venv\Scripts\python.exe` and repair the
  `openrouter-voice` profile when either import is missing.
- Distinguish mock adapters from real microphone/audio adapters in status UI.
- Replay the latest task cards when the browser dashboard opens late.

## Acceptance criteria

- [ ] Only the avatar and its compact top toolbar are visible natively.
- [ ] Dragging the unlocked grip moves both docked windows and persists the
      avatar position.
- [ ] Locking prevents movement and survives a restart.
- [ ] The avatar and toolbar remain always-on-top.
- [ ] The gear and `Ctrl+Shift+O` open the local dashboard in the default
      browser.
- [ ] The X control cleanly exits the desktop process.
- [ ] Holding the microphone or `Ctrl+Space` records one PTT turn; releasing it
      submits the final transcript.
- [ ] Auto listen transcribes ordinary speech with no wake name.
- [ ] Starting PTT while Auto listen is active pauses and later restores Auto
      listen.
- [ ] Disabling agent voice suppresses subsequent TTS and interrupts current
      playback.
- [ ] Missing RealtimeSTT/RealtimeTTS produces the exact project repair command.
- [ ] Dashboard voice status reports mock versus real input/output accurately.
- [ ] Dashboard chat, settings, task replay/cancel, diagnostics, and WebSocket
      reconnect work.
- [ ] Python, frontend, configuration, import-boundary, and pack checks pass.
- [ ] Native Rust checks pass on a Rust-equipped Windows or CI runner.

## Prepared patch evidence

- Python: 471 passed, 30 source-only contract registrations skipped.
- Frontend: 16 files / 88 tests passed; TypeScript and Vite production build
  passed.
- Ruff lint passed across `apps`, `packages`, `tests`, and `scripts`.
- Base config plus every shipped profile validated.
- Character packs validated; the optional VRM pack retains one known
  `speaking_frames` fallback warning.
- Dashboard assets, health, appearance, WebSocket voice status, chat, runtime
  swap, and continuous-mode toggle passed backend smoke checks.
- Native Tauri compilation remains for a machine with `cargo` and `rustfmt`;
  those tools are unavailable in the preparation environment.

## Branch and merge workflow

Use `dev` as the integration branch:

```bash
git fetch origin
git switch dev
git pull --ff-only origin dev
git switch -c feat/issue-<NUMBER>-avatar-toolbar-voice-v1.2.0
```

If `dev` does not exist yet:

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c dev
git push -u origin dev
git switch -c feat/issue-<NUMBER>-avatar-toolbar-voice-v1.2.0
```

Apply the versioned source ZIP on the task branch, review the diff, then:

```bash
git add -A
git commit -m "feat(desktop): add avatar toolbar and continuous voice for v1.2.0"
git push -u origin feat/issue-<NUMBER>-avatar-toolbar-voice-v1.2.0
```

Open a pull request from the task branch into `dev`. After approval, merge and
verify the integration branch:

```bash
git switch dev
git pull --ff-only origin dev
git merge --no-ff feat/issue-<NUMBER>-avatar-toolbar-voice-v1.2.0
git push origin dev
```

Create a `dev` → `main` release PR. Tag only after that PR and the native Rust
checks pass:

```bash
git switch main
git pull --ff-only origin main
git tag -a v1.2.0 -m "OpenMimicry v1.2.0"
git push origin v1.2.0
```
