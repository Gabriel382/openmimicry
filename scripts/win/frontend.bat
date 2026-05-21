@echo off
REM OpenMimicry — Vite dev server on :5173.
where make >nul 2>nul && ( make frontend & exit /b )
pnpm.cmd --filter @openmimicry/desktop-frontend dev
