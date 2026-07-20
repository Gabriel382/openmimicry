@echo off
REM OpenMimicry — workspace install (Windows). Mirrors `make install`.
setlocal enableextensions enabledelayedexpansion

for %%I in ("%~dp0\..\..") do set "REPO_ROOT=%%~fI"
pushd "%REPO_ROOT%" || goto :error

set "PROFILE=%~1"
if "%PROFILE%"=="" set "PROFILE=basic"

REM where make >nul 2>nul
REM if %errorlevel%==0 (
REM     make install PROFILE=%PROFILE%
REM     goto :eof
REM )

REM ----- Fallback path when GNU make isn't available ---------------------
if defined OPENMIMICRY_VENV (
    for %%I in ("%OPENMIMICRY_VENV%") do set "VENV=%%~fI"
) else (
    set "VENV=%REPO_ROOT%\.venv"
)
set "NEW_VENV=0"
if not exist "%VENV%\Scripts\python.exe" (
    python -m venv "%VENV%" || goto :error
    set "NEW_VENV=1"
)
set "PY=%VENV%\Scripts\python.exe"

set "CLAIM_ARG="
if "!NEW_VENV!"=="1" set "CLAIM_ARG=--claim"
if /i "%OPENMIMICRY_CLAIM_EXISTING_VENV%"=="1" set "CLAIM_ARG=--claim"
"%PY%" scripts\validate_install_environment.py --repo-root "%REPO_ROOT%" !CLAIM_ARG! || goto :error

"%PY%" -m pip install --upgrade pip setuptools wheel || goto :error
"%PY%" -m pip install -e packages\openmimicry-core      || goto :error
"%PY%" -m pip install -e packages\openmimicry-llm       || goto :error
"%PY%" -m pip install -e packages\openmimicry-memory    || goto :error
"%PY%" -m pip install -e packages\openmimicry-voice     || goto :error
if /i "%PROFILE%"=="voice" "%PY%" -m pip install -e "packages\openmimicry-voice[voice,piper-community]" || goto :error
if /i "%PROFILE%"=="openrouter-voice" (
    "%PY%" -m pip install -e "packages\openmimicry-llm[litellm]" || goto :error
    "%PY%" -m pip install -e "packages\openmimicry-voice[voice,piper-community]" || goto :error
)
if /i "%PROFILE%"=="openrouter-commercial" (
    "%PY%" -m pip install -e "packages\openmimicry-llm[litellm]" || goto :error
    "%PY%" -m pip install -e "packages\openmimicry-voice[voice]" || goto :error
)
if /i "%PROFILE%"=="openrouter-chatterbox" (
    "%PY%" -m pip install -e "packages\openmimicry-llm[litellm]" || goto :error
    "%PY%" -m pip install -e "packages\openmimicry-voice[voice,clone-chatterbox]" || goto :error
    "%PY%" scripts\install_chatterbox_runtime.py --python "%PY%" || goto :error
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
popd
goto :eof

:error
set "INSTALL_ERROR=%errorlevel%"
if "%INSTALL_ERROR%"=="0" set "INSTALL_ERROR=1"
popd 2>nul
echo Install failed (errorlevel=%INSTALL_ERROR%).
exit /b %INSTALL_ERROR%
