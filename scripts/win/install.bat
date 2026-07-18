@echo off
REM OpenMimicry — workspace install (Windows). Mirrors `make install`.
setlocal enableextensions enabledelayedexpansion

set "PROFILE=%~1"
if "%PROFILE%"=="" set "PROFILE=basic"

REM where make >nul 2>nul
REM if %errorlevel%==0 (
REM     make install PROFILE=%PROFILE%
REM     goto :eof
REM )

REM ----- Fallback path when GNU make isn't available ---------------------
set "VENV=.venv"
if not exist "%VENV%\Scripts\python.exe" (
    python -m venv "%VENV%" || goto :error
)
set "PY=%VENV%\Scripts\python.exe"

"%PY%" -m pip install --upgrade pip setuptools wheel || goto :error
"%PY%" -m pip install -e packages\openmimicry-core      || goto :error
"%PY%" -m pip install -e packages\openmimicry-llm       || goto :error
"%PY%" -m pip install -e packages\openmimicry-voice     || goto :error
if /i "%PROFILE%"=="voice" "%PY%" -m pip install -e "packages\openmimicry-voice[voice]" || goto :error
if /i "%PROFILE%"=="openrouter-voice" (
    "%PY%" -m pip install -e "packages\openmimicry-llm[litellm]" || goto :error
    "%PY%" -m pip install -e "packages\openmimicry-voice[voice]" || goto :error
)
"%PY%" -m pip install -e packages\openmimicry-avatar    || goto :error
"%PY%" -m pip install -e packages\openmimicry-tasks     || goto :error
if exist packages\openmimicry-vision (
    if /i "%PROFILE%"=="vision" "%PY%" -m pip install -e packages\openmimicry-vision || goto :error
    if /i "%PROFILE%"=="full-vision" "%PY%" -m pip install -e packages\openmimicry-vision || goto :error
)
if exist apps\backend\pyproject.toml "%PY%" -m pip install -e apps\backend || goto :error
"%PY%" -m pip install -e ".[dev]" || goto :error

if exist apps\desktop\frontend\package.json (
    where pnpm.cmd >nul 2>nul && pnpm.cmd install --frozen-lockfile
)

echo.
echo OpenMimicry installed (PROFILE=%PROFILE%)
goto :eof

:error
echo Install failed (errorlevel=%errorlevel%).
exit /b %errorlevel%
