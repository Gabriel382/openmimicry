"""Inspect and switch among configured LLM backends without exposing secrets."""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from openmimicry.core import ConfigUpdated
from pydantic import BaseModel, Field, SecretStr

from ..provider_catalog import CatalogError, discover_models
from ..user_settings import persist_llm_backend, persist_llm_model, persist_llm_web_search

__all__ = ["LLMBackendRequest", "LLMCredentialRequest", "LLMModelRequest", "router"]


class LLMBackendRequest(BaseModel):
    backend: str = Field(min_length=1, max_length=64)


class LLMModelRequest(BaseModel):
    backend: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=256)


class LLMCredentialRequest(BaseModel):
    backend: str = Field(min_length=1, max_length=64)
    action: str = Field(pattern="^(set|clear)$")
    token: SecretStr | None = None


class LLMWebSearchRequest(BaseModel):
    backend: str = Field(min_length=1, max_length=64)
    mode: str = Field(pattern="^(off|auto|always)$")


router = APIRouter()


@router.get("/llm/settings")
async def llm_settings(request: Request) -> dict[str, object]:
    llm = request.app.state.wiring.llm
    profiles = getattr(llm, "profiles", None)
    if not isinstance(profiles, dict):
        model = getattr(getattr(llm, "_settings", None), "model", "unknown")
        profiles = {"default": {"adapter": llm.name, "model": model}}
    config = request.app.state.config
    configured = config.llm.backends
    enriched: dict[str, dict[str, object]] = {}
    for name, profile in profiles.items():
        backend_config = configured.get(name)
        provider = backend_config.provider if backend_config is not None else "unknown"
        api_base = backend_config.api_base if backend_config is not None else None
        credential = {"session": False, "environment": False}
        credential_status = getattr(llm, "credential_status", None)
        if callable(credential_status):
            with suppress(ValueError):
                credential = credential_status(name)
        enriched[name] = {
            **profile,
            "provider": provider,
            "api_base": api_base,
            "credentials": credential,
        }
    return {
        "active_backend": getattr(llm, "active_backend", next(iter(profiles))),
        "active_model": getattr(
            llm,
            "active_model",
            profiles[next(iter(profiles))].get("model", "unknown"),
        ),
        "backends": enriched,
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


@router.get("/llm/catalog")
async def llm_catalog(
    request: Request,
    backend: str = Query(min_length=1, max_length=64),
) -> dict[str, object]:
    config = request.app.state.config
    backend_config = config.llm.backends.get(backend)
    if backend_config is None:
        raise HTTPException(status_code=404, detail=f"unknown LLM backend {backend!r}")
    try:
        models = await discover_models(
            backend_config.provider,
            api_base=backend_config.api_base,
        )
    except CatalogError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"backend": backend, "provider": backend_config.provider, "models": models}


@router.post("/llm/model")
async def update_llm_model(req: LLMModelRequest, request: Request) -> dict[str, object]:
    llm = request.app.state.wiring.llm
    selector = getattr(llm, "select_model", None)
    if not callable(selector):
        raise HTTPException(status_code=409, detail="runtime model selection is unavailable")
    try:
        selector(req.backend, req.model)
        persist_llm_model(req.backend, req.model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await llm_settings(request)


@router.post("/llm/credentials")
async def update_llm_credentials(req: LLMCredentialRequest, request: Request) -> dict[str, object]:
    """Set or clear an in-memory key. The token is never written to disk."""

    llm = request.app.state.wiring.llm
    try:
        if req.action == "clear":
            clearer = getattr(llm, "clear_session_api_key", None)
            if not callable(clearer):
                raise ValueError("this LLM configuration does not accept session credentials")
            clearer(req.backend)
        else:
            if req.token is None:
                raise ValueError("token is required when action is 'set'")
            setter = getattr(llm, "set_session_api_key", None)
            if not callable(setter):
                raise ValueError("this LLM configuration does not accept session credentials")
            setter(req.backend, req.token.get_secret_value())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await llm_settings(request)


@router.post("/llm/web-search")
async def update_web_search(req: LLMWebSearchRequest, request: Request) -> dict[str, object]:
    setter = getattr(request.app.state.wiring.llm, "set_web_search_mode", None)
    if not callable(setter):
        raise HTTPException(status_code=409, detail="web search is unavailable")
    try:
        setter(req.backend, req.mode)
        persist_llm_web_search(req.backend, req.mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await llm_settings(request)
