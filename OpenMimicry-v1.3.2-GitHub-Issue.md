# Stabilize multi-turn voice, STT endpointing, and desktop reply events

## Problem

Windows testing of v1.3.1 exposed four related lifecycle defects:

1. RealtimeSTT finalises after a very short silence, so a natural pause can
   submit an incomplete phrase.
2. RealtimeTTS calls `play_async()` and immediately trusts `is_playing()`.
   After the first reply this value can still be false during startup, so the
   adapter reports completion and later replies produce no audible playback.
3. React development remounts can leave a stale WebSocket dispatching events.
   The bubble therefore receives the same delta twice, and the Vite WS proxy
   reports `ECONNABORTED` during socket teardown.
4. The speech bubble has overflow styling but the native avatar window is
   click-through, so the user cannot operate its scrollbar.

Windows shutdown may also emit WebView2 error 1412 while Chromium unregisters
`Chrome_WidgetWin_0` during process teardown.

## Required change

- Add `voice.stt.post_speech_silence_duration`, default `1.0` second and
  bounded to `0.2`–`3.0`, pass it to RealtimeSTT, and expose/persist it from the
  localhost dashboard.
- Restart active wake/continuous listening safely when the value changes;
  apply it to the next PTT recording without requiring a backend restart.
- Treat RealtimeTTS playback as one blocking transaction on a worker thread;
  do not infer completion from `is_playing()` immediately after `play_async()`.
- Start TTS and publish the same complete display text together. Do not split
  an already-collected structured reply into artificial append-only chunks.
- Give each frontend WebSocket a generation and ignore callbacks from stale
  generations. Connect Tauri/Vite desktop windows directly to port 8000 rather
  than proxying `/ws` through Vite.
- Add a toolbar control that toggles the avatar window between click-through
  and reply-interaction mode. Auto-follow new bubble text and keep the bubble
  keyboard focusable and scrollable.
- Explicitly close all three webview windows before `app.exit(0)`.

## Acceptance criteria

- A sentence containing a natural 0.5–0.9 second pause is not cut off with the
  default endpoint setting.
- The dashboard can save a value from `0.2` through `3.0`, persists it in
  `config/user.yaml`, and rejects values outside the range.
- At least five consecutive typed or spoken LLM replies each produce audio
  when Agent voice is enabled.
- Each reply appears exactly once in the desktop bubble and once in dashboard
  conversation history.
- Text appears when TTS begins instead of waiting until audio completes.
- Three desktop windows result in three stable backend WebSockets, not six.
- The reply-interaction button permits mouse-wheel, scrollbar, and keyboard
  scrolling; disabling it restores click-through behavior.
- Normal desktop development no longer routes WebSockets through Vite and
  does not produce the reported Vite `ECONNABORTED` proxy error.
- Toolbar exit closes the webview windows before terminating the app.
- Python, frontend, build, config, and pack regression checks pass.

## Implementation branch

```powershell
git switch dev
git pull --ff-only
git switch -c fix/v1.3.2-voice-lifecycle
```

Commit and merge the completed task into `dev`:

```powershell
git add .
git commit -m "fix: stabilize voice playback and desktop event lifecycle"
git switch dev
git merge --no-ff fix/v1.3.2-voice-lifecycle
```

Create a separate collaborator-review/release branch from the updated `dev`:

```powershell
git switch -c release/v1.3.2 dev
git push -u origin release/v1.3.2
```

After review, merge and tag according to repository policy:

```powershell
git switch dev
git merge --no-ff release/v1.3.2
git tag -a v1.3.2 -m "OpenMimicry v1.3.2"
git push origin dev v1.3.2
```

## Versioning

Ship as `v1.3.2`. This is a SemVer patch: it repairs runtime behavior and adds
only backward-compatible configuration/API fields.
