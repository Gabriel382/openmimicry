# OpenMimicry v1.4.2 release notes

v1.4.2 addresses the Windows trace in which the first voice turn completed,
then RealtimeTTS printed `Immediate stop requested, aborting playback` and the
application remained in transcription indefinitely.

## What changed

- `TextToAudioStream.stop()` now runs on a bounded daemon helper rather than
  the asyncio event loop. A blocking audio driver can no longer freeze STT,
  text input, WebSockets, or the mode controls.
- A TTS worker that does not drain is retired and replaced. The replacement
  owns a new SystemEngine/COM apartment, allowing the next answer to speak.
- PTT interruption has a 150 ms settle budget. Microphone capture proceeds
  while any slower third-party audio cleanup completes independently.
- Realtime STT partial previews are coalesced. Every final transcript has
  priority and is delivered immediately to continuous/wake handling.
- Passive-listener logs now distinguish recorder receipt from controller
  dequeue and accepted/rejected wake processing.

## Expected live-wake behavior

Live wake remains name-gated. Each completed phrase beginning with a configured
name or alias—such as `Mimi, tell me a joke`—is finalized, displayed, and sent
to the LLM immediately. Disabling live wake is not required to trigger
transcription or submission. Phrases without the name remain visible in
history but are not sent to the LLM.

## Diagnostics

Use **Settings → Diagnostics → Download bundle**, or run:

```powershell
.\scripts\win\collect-diagnostics.bat
```

The bundle excludes `.env` and API-key values. Review transcripts and local
paths before sharing it.

## Compatibility

This is a backward-compatible patch over v1.4.1. Configuration and stable core
contracts are unchanged.

## Validation

- 548 Python tests passed.
- 92 desktop frontend tests passed across 17 files.
- Pyright, Ruff lint/format, import-boundary checks, JavaScript syntax, pack
  validation, TypeScript compilation, and the Vite production build passed.
- The blocking-stop regression uses a stream whose `stop()` and `play()` do
  not return, and confirms PTT remains responsive and reply two uses a new
  worker lane.
- Windows microphone, SAPI, and COM behavior still requires the hardware
  matrix below because the release environment has no Windows audio devices.

See `docs/V1.4.2_WINDOWS_TESTING.md` for the acceptance matrix.
