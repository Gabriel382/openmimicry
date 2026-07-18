"""Inspect and switch among configured LLM backends without exposing secrets."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from openmimicry.core import ConfigUpdated
from pydantic import BaseModel, Field

from ..user_settings import persist_llm_backend

__all__ = ["LLMBackendRequest", "router"]


class LLMBackendRequest(BaseModel):
    backend: str = Field(min_length=1, max_length=64)


router = APIRouter()


@router.get("/llm/settings")
async def llm_settings(request: Request) -> dict[str, object]:
    llm = request.app.state.wiring.llm
    profiles = getattr(llm, "profiles", None)
    if not isinstance(profiles, dict):
        model = getattr(getattr(llm, "_settings", None), "model", "unknown")
        profiles = {"default": {"adapter": llm.name, "model": model}}
    return {
        "active_backend": getattr(llm, "active_backend", next(iter(profiles))),
        "active_model": getattr(
            llm,
            "active_model",
            profiles[next(iter(profiles))].get("model", "unknown"),
        ),
        "backends": profiles,
    }


@router.post("/llm/settings")
async def update_llm_settings(req: LLMBackendRequest, request: Request) -> dict[str, object]:
    wiring = request.app.state.wiring
    selector = getattr(wiring.llm, "select", None)
    if not callable(selector):
        raise HTTPException(
            status_code=409,
            detail="this configuration has only one LLM backend",
        )
    try:
        selector(req.backend)
        persist_llm_backend(req.backend)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    wiring.bus.publish(
        ConfigUpdated(
            ts=datetime.now(timezone.utc),
            diff={
                "llm_backend": wiring.llm.active_backend,
                "llm_model": wiring.llm.active_model,
            },
        )
    )
    return await llm_settings(request)
