# OpenMimicry v1.3.1 — voice turn completion and history

## Outcome

v1.3.1 fixes the reported voice path without changing the OpenRouter setup.
The supplied log proves STT reached the LLM: LiteLLM calls appear immediately
after voice processing at 01:41:22 and 01:44:18. The actual failure follows at
01:44:18: RealtimeSTT hears Windows system TTS, the barge-in watcher cancels
playback, and `asyncio.CancelledError` escapes the WebSocket handler before the
final reply/avatar events are published.

The safe default now pauses passive listening during TTS, intentional audio
interruptions cannot abandon a chat turn, and PTT exposes every stage and its
recognized text.

## Included changes

- New LLM turns clear incomplete prior bubble text before streaming the new
  reply.
- TTS cancellation is contained so `LLMReplyComplete` and the structured
  emotion/action `AvatarCue` are always published.
- Passive wake/continuous listening pauses during system TTS and resumes after
  playback; this prevents feedback transcripts and audio-queue growth.
- Automatic VAD barge-in is now opt-in with
  `voice.modes.barge_in_enabled: true`. PTT still interrupts TTS.
- PTT reports `listening` while held, `transcribing` after release, and then the
  recognized transcript or an explicit no-speech result.
- The localhost dashboard replays the latest 100 typed, recognized voice, and
  assistant turns. This history is intentionally process-memory only.
- The Windows voice launcher detects an existing listener on port 8000 and
  reports its process ID instead of exposing a raw Uvicorn bind traceback.
- All first-party packages and applications are versioned `1.3.1`.

## Recommended Git issue

**Title:** Fix RealtimeSTT/TTS self-hearing, incomplete turns, and opaque PTT

**Body:**

> RealtimeSTT hears the agent's Windows system TTS, triggers automatic
> barge-in, and cancels the reply. `asyncio.CancelledError` then escapes the
> WebSocket request path before `LLMReplyComplete` and `AvatarCue`, leaving an
> incomplete bubble and an avatar that can remain on a speaking frame. Make
> speaker-safe behavior the default, retain explicit PTT interruption, expose
> PTT transcription stages/results, and show typed/voice input in replayable
> dashboard history. Detect duplicate port-8000 backends before launch.
>
> Acceptance criteria:
> - Every LLM turn resets incomplete prior bubble text.
> - Intentional TTS cancellation never disconnects the chat WebSocket or skips
>   final reply/avatar events.
> - Default passive STT cannot transcribe the agent's own TTS.
> - PTT visibly progresses from listening to transcribing to a transcript or
>   no-speech result.
> - Dashboard history distinguishes text, voice, and assistant turns.
> - Wake listening resumes after TTS and continues to require the configured
>   name.
> - A second backend launch reports the process holding port 8000.
> - Python and frontend regression suites pass.

## Branch and merge workflow

Create the implementation branch from `dev`:

```powershell
git switch dev
git pull --ff-only
git switch -c fix/v1.3.1-voice-turn-completion
```

After local Windows verification, merge the task branch into `dev`:

```powershell
git add .
git commit -m "fix: complete voice turns and expose transcription state"
git switch dev
git merge --no-ff fix/v1.3.1-voice-turn-completion
```

Create a separate release/merge branch from the updated `dev`:

```powershell
git switch -c release/v1.3.1 dev
git push -u origin release/v1.3.1
```

After collaborator review, merge that branch according to repository policy,
then tag the release:

```powershell
git switch dev
git merge --no-ff release/v1.3.1
git tag -a v1.3.1 -m "OpenMimicry v1.3.1"
git push origin dev v1.3.1
```

This is a SemVer patch release: it corrects runtime behavior and adds only
backward-compatible wire/config fields.

## Start and verify

Start one voice backend, then the desktop in a second terminal:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-voice.ps1
.\scripts\win\desktop.bat
```

See [`docs/V1.3.1_WINDOWS_TESTING.md`](docs/V1.3.1_WINDOWS_TESTING.md) for the
exact PTT, wake-listen, history, and avatar-state checks.
