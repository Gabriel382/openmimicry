@echo off
REM OpenMimicry — toolchain checklist.
where make >nul 2>nul && ( make doctor & exit /b )
set "VENV=.venv"
if exist "%VENV%\Scripts\python.exe" (
    "%VENV%\Scripts\python.exe" scripts\doctor.py
) else (
    python scripts\doctor.py
)
