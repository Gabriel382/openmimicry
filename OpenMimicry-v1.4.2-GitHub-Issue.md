# v1.4.2 — prevent infinite transcription after first voice turn

## Problem

On Windows with RealtimeTTS `SystemEngine`, the first PTT/STT/LLM/TTS turn can
work. Starting the next PTT turn invokes `TextToAudioStream.stop()`, prints
`Immediate stop requested, aborting playback`, and blocks the asyncio event
loop. Subsequent PTT, typed chat, WebSockets, and passive listening stop making
progress.

Live wake can also produce multiple `STT final received` lines without a
`SpeechController ... final dequeued` line. Realtime partial callbacks can
outpace UI/event-bus projection, leaving the final transcript behind a large
FIFO backlog until the listener is disabled.

## Scope

- Run third-party TTS stop operations outside the asyncio event loop.
- Bound PTT interruption and playback-worker cleanup.
- Replace a poisoned SystemEngine/COM worker before the next reply.
- Use daemon TTS lanes so an abandoned third-party worker cannot block process
  exit.
- Coalesce partial STT hypotheses and prioritize every final transcript.
- Add diagnostic logs and regressions for both reported failures.

## Acceptance criteria

- [x] A `stream.stop()` implementation that never returns cannot block PTT.
- [x] The second TTS turn plays on a replacement worker after the first worker
  fails to drain.
- [x] Typed/WebSocket work remains schedulable during audio cleanup.
- [x] At most one obsolete realtime partial waits ahead of a final transcript.
- [x] A final survives a flood of 500 partial updates and is consumed promptly.
- [x] Live wake sends each accepted, name-prefixed final without toggling the
  mode off.
- [x] Existing PTT, wake, voice, and backend integration tests remain green.
- [ ] Confirm the Windows hardware matrix in `docs/V1.4.2_WINDOWS_TESTING.md`.

## Branch and merge workflow

```bash
git switch dev
git pull --ff-only origin dev
git switch -c fix/v1.4.2-nonblocking-voice-loop

git add -A
git commit -m "fix: keep voice turns responsive across blocking audio stop"
git push -u origin fix/v1.4.2-nonblocking-voice-loop
```

Open a pull request from `fix/v1.4.2-nonblocking-voice-loop` into `dev`. After
review and green CI:

```bash
git switch dev
git pull --ff-only origin dev
git merge --ff-only fix/v1.4.2-nonblocking-voice-loop
git push origin dev
```

Promote `dev` through the normal release PR, then tag the release commit:

```bash
git tag -a v1.4.2 -m "OpenMimicry v1.4.2"
git push origin v1.4.2
```

Versioning rationale: v1.4.2 is a patch release. It changes adapter lifecycle
and scheduling behavior without altering public contracts or configuration
schema version 1.
