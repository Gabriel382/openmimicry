@echo off
REM OpenMimicry — purge the v0.x prototype tree.
REM Forwards to the PowerShell cleanup script.
powershell -ExecutionPolicy Bypass -File "%~dp0..\cleanup-legacy.ps1" -Apply
