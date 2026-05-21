@echo off
REM OpenMimicry — run the FastAPI backend on :8000.
setlocal enableextensions

where make >nul 2>nul
if %errorlevel%==0 (
    make backend
    goto :eof
)

set "VENV=.venv"
if exist "%VENV%\Scripts\python.exe" (
    "%VENV%\Scripts\python.exe" -m uvicorn openmimicry_backend.main:app --reload --port 8000
) else (
    python -m uvicorn openmimicry_backend.main:app --reload --port 8000
)
