@echo off
REM OpenMimicry — full test suite (pytest + Vitest).
setlocal enableextensions

where make >nul 2>nul && ( make test & make frontend-test & exit /b )

set "VENV=.venv"
if exist "%VENV%\Scripts\python.exe" (
    "%VENV%\Scripts\python.exe" -m pytest || exit /b %errorlevel%
) else (
    python -m pytest || exit /b %errorlevel%
)
pnpm.cmd --filter @openmimicry/desktop-frontend test
