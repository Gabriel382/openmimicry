# Windows `.bat` wrappers

Thin wrappers around the canonical `make` targets so the workflow
works identically in `cmd.exe` / PowerShell without requiring GNU
Make. Each script forwards arguments to `make` if it's on `PATH`;
otherwise it falls back to running the underlying command directly.

Run from the repo root:

```powershell
PS> .\scripts\win\install.bat                  # make install PROFILE=basic
PS> .\scripts\win\install.bat voice            # make install PROFILE=voice
PS> .\scripts\win\backend.bat                  # FastAPI on :8000
PS> .\scripts\win\frontend.bat                 # Vite on :5173
PS> .\scripts\win\desktop.bat                  # cargo tauri dev
PS> .\scripts\win\doctor.bat                   # toolchain checklist
PS> .\scripts\win\test.bat                     # pytest + Vitest
PS> .\scripts\win\docker-up.bat                # docker compose up backend
PS> .\scripts\win\cleanup-legacy.bat           # purge v0.x prototype dirs
```

If you have Make installed (via Chocolatey, scoop, or Git for Windows),
prefer `make <target>` directly — these wrappers exist for the
Make-free path.
