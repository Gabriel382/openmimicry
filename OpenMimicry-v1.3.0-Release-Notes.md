# OpenMimicry v1.3.0 — Windows voice and companion controls

## Outcome

v1.3.0 fixes the Windows voice session restart seen after `loaded engine
system`, makes hands-free speech explicitly name-gated, keeps text independent
of voice, and places interactive controls above and below the click-through
avatar.

## Included changes

- Voice-safe Windows launcher runs Uvicorn without reload. First-use
  `comtypes` generation can no longer restart the backend during TTS.
- WebSocket shutdown handles Starlette's disconnected-state `RuntimeError`
  without an ASGI traceback.
- PTT waits up to eight seconds for the final transcript on Windows CPU/first
  run.
- Wake listen accepts only utterances beginning with the configured name,
  default `Mimi`; the name is removed before LLM submission.
- Wake name is editable in the localhost dashboard and persisted in ignored
  `config/user.yaml`.
- Top toolbar contains drag, lock, PTT, wake listen, agent voice, settings, and
  exit. A separate composer is docked below the avatar.
- Typed and spoken LLM turns show a perceptible thinking animation.
- Structured LLM emotion/action cues remain active and allow-listed.
- All first-party packages and applications are versioned `1.3.0`.

## Recommended Git issue

**Title:** Stabilize Windows voice and add configurable name-gated companion UI

**Body:**

> Prevent Windows system-TTS COM generation from triggering backend reloads;
> handle shutdown WebSocket races; keep text usable with voice enabled; expose
> PTT and configurable name-gated wake listening; show thinking for typed and
> spoken turns; split the desktop companion into a top control toolbar,
> click-through avatar, and bottom composer. Persist the wake name without
> committing user configuration. Add regression tests and Windows instructions.
>
> Acceptance criteria:
> - First spoken reply does not restart Uvicorn or disconnect the desktop.
> - PTT accepts speech without a name.
> - Wake listen ignores ordinary speech and accepts `Mimi, <command>`.
> - Wake name is dashboard-editable and survives restart.
> - Text works whether agent voice is on or off.
> - Thinking animation appears for text and voice turns.
> - Toolbar is above, composer below, and all surfaces stay synchronized and
>   always on top.

Suggested issue branch:

```powershell
git switch dev
git pull --ff-only
git switch -c fix/v1.3.0-windows-voice-wake-layout
```

After review and local verification:

```powershell
git add .
git commit -m "fix: stabilize voice and add name-gated companion controls"
git switch dev
git merge --no-ff fix/v1.3.0-windows-voice-wake-layout
git tag -a v1.3.0 -m "OpenMimicry v1.3.0"
```

Use a separate release/merge branch only if the repository policy requires it:

```powershell
git switch -c release/v1.3.0 dev
```

## Start order

Extract into a clean folder and preserve only `.env` from the previous copy.
Install/update, then start the voice backend first:

```powershell
.\scripts\win\install.bat openrouter-voice
powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-voice.ps1
```

Wait for `Application startup complete`, then launch the desktop in a second
terminal:

```powershell
.\scripts\win\desktop.bat
```

See `docs/V1.3_WINDOWS_TESTING.md` for the test matrix and first-run model notes.

