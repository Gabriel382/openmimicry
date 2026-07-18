# v1.4.1 — recover repeat voice turns and add actionable diagnostics

## Problem

On Windows, the first STT → LLM → TTS interaction can succeed and then leave
OpenMimicry unable to speak, accept another continuous-listening utterance, or
display later typed input. The reported trace also contains an ASGI exception
from sending the initial WebSocket status after the client already closed.

## Confirmed causes

1. Cancelling an asyncio task awaiting `run_in_executor()` did not stop or
   drain the underlying RealtimeTTS worker. The next playback queued behind the
   abandoned Windows COM job.
2. TTS readiness was stored on the adapter, allowing reply two to observe
   reply one's already-completed readiness event.
3. Normal passive-listener pauses called recorder control methods and posted an
   iterator sentinel asynchronously. A quick restart could begin before that
   sentinel arrived, after which the stale sentinel terminated session two.
4. The ordered conversation lock was held through TTS completion and the
   WebSocket receive loop awaited that operation, coupling audio health to text
   input responsiveness.
5. WebSocket replay/status, bus projection, and avatar output could write to
   the same socket without one serialized send lane; close races escaped from
   the initial status send.

## Scope

- Make RealtimeTTS cancellation drain the real worker before reuse.
- Give every reply its own readiness future and add a conservative watchdog.
- Pause/abort STT without destroying its warm recorder; reserve shutdown for
  recorder replacement or application exit.
- Preserve ordered LLM turns while queuing input independently from UI I/O.
- Serialize per-socket writes and contain every disconnect race.
- Persist correlated diagnostics and expose a sanitized downloadable bundle.

## Acceptance criteria

- [x] Three sequential typed turns appear immediately and all three replies
  complete even if TTS fails.
- [x] Cancelling reply one cannot block reply two's executor playback.
- [x] PTT/continuous capture can stop and restart on the same warm recorder.
- [x] A stale stop sentinel cannot terminate a newly started STT iterator.
- [x] Passive STT restores after each completed, interrupted, or timed-out TTS.
- [x] Initial status/replay sends racing with socket close do not raise from the
  ASGI application.
- [x] Concurrent outbound messages never overlap writes on the same socket.
- [x] The dashboard downloads a versioned diagnostic ZIP without `.env` or API
  key values.
- [x] The Windows checklist covers text, PTT, continuous, interruption, and
  reconnect runs without restarting the backend.
- [x] Full Python/frontend validation, lint, typing, and builds pass.

## Branch and merge workflow

```bash
git switch dev
git pull --ff-only origin dev
git switch -c fix/v1.4.1-repeat-voice-lifecycle

git add -A
git commit -m "fix: recover repeat voice turns and add diagnostics"
git push -u origin fix/v1.4.1-repeat-voice-lifecycle
```

Open a pull request from `fix/v1.4.1-repeat-voice-lifecycle` into `dev`. After
review and green CI:

```bash
git switch dev
git pull --ff-only origin dev
git merge --ff-only fix/v1.4.1-repeat-voice-lifecycle
git push origin dev
```

Promote `dev` through the normal release PR, then tag the release commit:

```bash
git tag -a v1.4.1 -m "OpenMimicry v1.4.1"
git push origin v1.4.1
```

Versioning rationale: v1.4.1 is a patch release. It repairs v1.4.0 lifecycle
and transport behavior without breaking the frozen v1 contracts or changing
configuration schema version 1. The diagnostic endpoint/UI is additive.
