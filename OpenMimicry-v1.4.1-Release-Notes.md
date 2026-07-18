# OpenMimicry v1.4.1 release notes

v1.4.1 fixes the repeat-turn freeze seen on Windows after the first successful
voice reply and makes any remaining device-specific problem diagnosable in one
download.

## What changed

- Interrupted RealtimeTTS playback now stops and drains its actual executor
  job before another reply can use the Windows COM worker.
- Each answer owns a fresh audio-readiness signal. A bounded watchdog restores
  listening if an audio driver or TTS stream never completes.
- RealtimeSTT ordinary pauses retain the prewarmed recorder. Session-stop
  sentinels can no longer arrive late and terminate the next listening turn.
- Typed and voice turns remain ordered, but WebSocket input no longer waits for
  LLM/TTS completion. Audio failure therefore cannot freeze the chat box.
- WebSocket writes are serialized per connection and close races are handled
  as normal disconnects.
- The dashboard can download a sanitized diagnostic ZIP with numbered turn,
  STT, TTS, and socket lifecycles plus dependency/runtime metadata.

## Diagnostics

Use **Settings → Diagnostics → Download bundle**. If the backend page is not
available, run:

```powershell
.\scripts\win\collect-diagnostics.bat
```

The collector excludes `.env` and API-key values. It may contain local paths
and recognized transcripts, so review the ZIP before sharing it.

## Compatibility

This is a backward-compatible patch over v1.4.0. Contract and configuration
schema versions remain unchanged. OpenRouter `openai/gpt-4o-mini`, Ollama
switching, bounded conversation memory, and character-pack ZIP import keep
their v1.4.0 behavior.

## Validation

- 545 Python tests passed.
- 92 desktop frontend tests passed across 17 files.
- Pyright, Ruff lint/format, import-boundary checks, JavaScript syntax, pack
  validation, TypeScript compilation, and the Vite production build passed.
- Windows audio-device behavior must still be confirmed with the repeat-turn
  matrix below because the release environment has no Windows microphone or
  SAPI output device.

See `docs/V1.4.1_WINDOWS_TESTING.md` for the repeat-turn acceptance matrix.
