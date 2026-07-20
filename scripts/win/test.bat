@echo off
REM OpenMimicry — full test suite (pytest + Vitest).
setlocal enableextensions

for %%I in ("%~dp0\..\..") do set "REPO_ROOT=%%~fI"
pushd "%REPO_ROOT%" || exit /b 1
if defined OPENMIMICRY_VENV (
    for %%I in ("%OPENMIMICRY_VENV%") do set "VENV=%%~fI"
) else (
    set "VENV=%REPO_ROOT%\.venv"
)
if not exist "%VENV%\Scripts\python.exe" (
    echo OpenMimicry Python environment not found: %VENV%\Scripts\python.exe
    popd
    exit /b 1
)
"%VENV%\Scripts\python.exe" -m pytest
if errorlevel 1 goto :error
pnpm.cmd --filter @openmimicry/desktop-frontend test
set "TEST_ERROR=%errorlevel%"
popd
exit /b %TEST_ERROR%

:error
set "TEST_ERROR=%errorlevel%"
popd
exit /b %TEST_ERROR%
