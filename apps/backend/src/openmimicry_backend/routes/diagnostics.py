"""Download the current sanitized diagnostic session as a ZIP."""

from __future__ import annotations

import io

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..diagnostics import build_diagnostic_bundle

__all__ = ["router"]


router = APIRouter()


@router.get("/diagnostics/bundle")
async def diagnostic_bundle(request: Request) -> StreamingResponse:
    session = request.app.state.diagnostics
    config = request.app.state.wiring.runtime.config
    status = request.app.state.get_mode_status()
    payload = build_diagnostic_bundle(
        session=session,
        config=config,
        runtime_status=status,
    )
    filename = f"OpenMimicry-diagnostics-{session.session_id}.zip"
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
