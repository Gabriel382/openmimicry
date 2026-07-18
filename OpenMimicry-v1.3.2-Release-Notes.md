# OpenMimicry v1.3.2 — reliable multi-turn voice

## Outcome

v1.3.2 stabilizes the complete voice-to-avatar turn. Natural pauses no longer
have to use RealtimeSTT's aggressive upstream endpoint, every RealtimeTTS
reply is awaited through actual playback, and desktop development remounts can
no longer deliver duplicate bubble text from stale WebSockets.

Text is made visible as the matching voice begins. The reply remains in the
bubble under the existing reading-time formula and can now be scrolled by
enabling the new reply-interaction toolbar control.

## Included changes

- `voice.stt.post_speech_silence_duration` defaults to `1.0` second, accepts
  `0.2`–`3.0`, and is applied to PTT, wake, and continuous listening.
- The localhost Voice card edits the endpoint pause and persists it alongside
  the wake name in ignored `config/user.yaml`.
- RealtimeTTS uses `play()` on a worker thread. It remains cancellable without
  blocking FastAPI and does not use the racy post-`play_async()`
  `is_playing()` check.
- The parsed response is displayed once as TTS starts; the final bubble event
  replaces it after playback.
- Desktop WebSockets use generation ownership and connect straight to
  `ws://127.0.0.1:8000/ws`, eliminating stale StrictMode dispatch and the Vite
  WebSocket proxy path.
- The top toolbar adds a reply-interaction/scroll button. Bubble content
  auto-follows new text and accepts focus, wheel, scrollbar, and keyboard
  scrolling while interaction is on.
- Exit explicitly closes composer, avatar, then controls before terminating
  Tauri, mitigating the Windows WebView2 class-unregistration warning.
- All first-party packages and applications are versioned `1.3.2`.

## Git workflow

The ready-to-paste task is in
[`OpenMimicry-v1.3.2-GitHub-Issue.md`](OpenMimicry-v1.3.2-GitHub-Issue.md).
Use `fix/v1.3.2-voice-lifecycle` for implementation, merge it into `dev`, then
create `release/v1.3.2` from that updated `dev` for collaborator review.

## Start and verify on Windows

Start the voice backend and desktop in separate PowerShell windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-voice.ps1
.\scripts\win\desktop.bat
```

Follow [`docs/V1.3.2_WINDOWS_TESTING.md`](docs/V1.3.2_WINDOWS_TESTING.md) for
the endpoint-pause, repeated-audio, duplicate-text, scrolling, socket-count,
and shutdown checks.
