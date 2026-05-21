@echo off
REM OpenMimicry — Tauri shell (overlay + panel).
where make >nul 2>nul && ( make desktop & exit /b )
pushd apps\desktop\src-tauri
cargo tauri dev
popd
