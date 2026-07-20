# Windows `.bat` wrappers

Wrappers around the canonical workspace commands so the workflow works in
`cmd.exe` and PowerShell without requiring GNU Make.

Run from the repo root:

```powershell
PS> .\scripts\win\install.bat                  # make install PROFILE=basic
PS> .\scripts\win\install.bat voice            # make install PROFILE=voice
PS> .\scripts\win\install.bat openrouter-voice # OpenRouter + local STT/system TTS
PS> .\scripts\win\install.bat openrouter-chatterbox # OpenRouter + local cloned TTS
PS> .\scripts\win\backend.bat                  # FastAPI on :8000
PS> .\scripts\win\frontend.bat                 # Vite on :5173
PS> .\scripts\win\desktop.bat                  # cargo tauri dev
PS> .\scripts\win\doctor.bat                   # toolchain checklist
PS> .\scripts\win\collect-diagnostics.bat       # sanitized voice/runtime ZIP
PS> .\scripts\win\test.bat                     # pytest + Vitest
PS> .\scripts\win\docker-up.bat                # docker compose up backend
PS> .\scripts\win\cleanup-legacy.bat           # purge v0.x prototype dirs
PS> powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-voice.ps1
```

`start-openrouter-voice.ps1` is the single launcher for local voice. It reads
the dashboard selection and prepares either Piper or Chatterbox. For
Chatterbox it repairs incomplete Torch runtimes, performs a one-time model
prewarm, repairs the real Perth watermark implementation when required,
selects `openrouter-chatterbox`, and disables backend reloads. Set
`OPENMIMICRY_CHATTERBOX_PREFLIGHT=force` to repeat model prewarming or
`OPENMIMICRY_TORCH_CHANNEL=cpu|cu118|cu124|cu126` to override automatic Torch
wheel selection.

The Python installer and backend, voice, test, doctor, and diagnostic launchers
resolve the repository from their own script path and use that checkout's
`.venv`. Set `OPENMIMICRY_VENV` only when you want a different dedicated
environment. Existing non-empty environments are refused until they have been
explicitly claimed for this checkout:

```powershell
$env:OPENMIMICRY_CLAIM_EXISTING_VENV = "1" # one-time migration only
.\scripts\win\install.bat openrouter-chatterbox
Remove-Item Env:OPENMIMICRY_CLAIM_EXISTING_VENV
```

Do not claim an environment shared with another project. Create a clean
OpenMimicry `.venv` instead. The ownership marker prevents later OpenMimicry
installers from changing a different repository's dependency graph.

If you have Make installed (via Chocolatey, scoop, or Git for Windows),
prefer `make <target>` directly — these wrappers exist for the
Make-free path.
