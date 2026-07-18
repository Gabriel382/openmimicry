# OpenMimicry v1.2.1 — Windows voice preflight hotfix

## Fixed

- Windows PowerShell no longer aborts at the first Python stderr line when the
  launcher checks voice imports under `ErrorActionPreference=Stop`.
- The launcher captures `LASTEXITCODE`, repairs the environment when needed,
  and prints the full Python diagnostic if repair still fails.
- The voice profile now installs `RealtimeSTT[faster-whisper]` and
  `RealtimeTTS[system]`, matching the concrete local STT and system-TTS engines
  OpenMimicry selects.
- Preflight verifies `AudioToTextRecorder`, `TextToAudioStream`, and
  `SystemEngine`, not merely the two top-level package names.
- RealtimeSTT defaults to CPU/int8 for a portable Windows launch instead of
  assuming a CUDA runtime is installed.

## Upgrade

Replace the v1.2.0 source with v1.2.1, then run:

```powershell
.\scripts\win\install.bat openrouter-voice
powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-voice.ps1
```

An existing `.env` and `OPENROUTER_API_KEY` are preserved. Do not copy an old
`.venv` into the new source folder; let the installer update or create it.

## Validation boundary

Python regression tests and the complete project suite run in the preparation
environment. The PowerShell control flow has static regression coverage;
end-to-end microphone and system-speaker validation must run on Windows.
