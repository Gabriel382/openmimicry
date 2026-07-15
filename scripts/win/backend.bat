@echo off
REM OpenMimicry — run the FastAPI backend on :8000.
setlocal enableextensions

REM Real Windows TTS may generate COM bindings under .venv on first use.
REM The Uvicorn reloader must be disabled for that launch or WatchFiles will
REM restart the backend halfway through the reply and drop every WebSocket.
if /i "%~1"=="--no-reload" goto :no_reload

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
goto :eof

:no_reload
set "VENV=.venv"
if exist "%VENV%\Scripts\python.exe" (
    "%VENV%\Scripts\python.exe" -m uvicorn openmimicry_backend.main:app --port 8000
) else (
    python -m uvicorn openmimicry_backend.main:app --port 8000
)
