# OpenMimicry v1.2.2 — Windows Python 3.13 voice hotfix

## Root causes fixed

The v1.2.1 launcher passed a multiline Python program to Windows PowerShell as
the value of `python -c`. Windows PowerShell's native-command argument handling
removed the quotes around the diagnostic `print(...)`, producing the reported
`SyntaxError: '(' was never closed` before a valid import result was possible.

The subsequent direct import exposed a separate compatibility issue: Python
3.13 removed the standard `audioop` module, while RealtimeTTS imports pydub,
which expects `audioop` or its maintained compatibility port.

## Changes

- The voice preflight is now `scripts/check_voice_imports.py`; PowerShell runs
  the file directly and no longer serializes inline Python source.
- The `voice` and `realtimetts` extras install `audioop-lts>=0.2.2`
  automatically when `python_version >= '3.13'`.
- The launcher still captures complete native stderr, attempts one repair via
  the project installer, and re-runs the same import check before startup.
- Every workspace package and application is versioned `1.2.2`.

## Upgrade and start

Extract v1.2.2 into a clean folder. Preserve your `.env`, but do not copy an
old `.venv` into the new folder. From the repository root in PowerShell:

```powershell
.\scripts\win\install.bat openrouter-voice
powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-voice.ps1
```

The installer can also update an existing project `.venv`. For an immediate
repair of a Python 3.13+ v1.2.1 environment:

```powershell
.\.venv\Scripts\python.exe -m pip install "audioop-lts>=0.2.2"
```

The v1.2.1 launcher itself should still be replaced because its inline
PowerShell/Python quoting defect is independent of the missing module.

## Validation boundary

The automated Python and frontend suites validate the dependency marker,
file-based preflight wiring, application behavior, and builds in the release
environment. A live RealtimeSTT microphone and Windows system-TTS device must
be verified on the target Windows machine.
