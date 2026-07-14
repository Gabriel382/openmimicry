"""Safe public endpoint for desktop appearance settings."""

from __future__ import annotations

from fastapi import APIRouter, Request

__all__ = ["router"]


router = APIRouter()


@router.get("/appearance")
async def get_appearance(request: Request) -> dict[str, object]:
    appearance = request.app.state.appearance
    return {"appearance": appearance.model_dump(mode="json")}
