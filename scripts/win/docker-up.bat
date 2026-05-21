@echo off
REM OpenMimicry — docker compose up backend (mocks-only by default).
where make >nul 2>nul && ( make docker-up & exit /b )
docker compose up backend
