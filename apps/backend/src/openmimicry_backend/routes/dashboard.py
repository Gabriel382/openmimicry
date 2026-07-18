"""Browser-hosted control board for settings, voice status, chat, and tasks."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

__all__ = ["router"]


_STATIC = Path(__file__).resolve().parent.parent / "static"
router = APIRouter()


@router.get("/dashboard", include_in_schema=False)
async def dashboard() -> FileResponse:
    return FileResponse(_STATIC / "dashboard.html", media_type="text/html")


@router.get("/dashboard.css", include_in_schema=False)
async def dashboard_css() -> FileResponse:
    return FileResponse(_STATIC / "dashboard.css", media_type="text/css")


@router.get("/dashboard.js", include_in_schema=False)
async def dashboard_js() -> FileResponse:
    return FileResponse(_STATIC / "dashboard.js", media_type="text/javascript")
