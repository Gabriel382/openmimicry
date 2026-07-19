"""Inspect, edit, delete, and export explicitly enabled long-term memory."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from openmimicry.core.schemas.app import MemoryConfig
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..user_settings import persist_memory_settings

__all__ = ["router"]


router = APIRouter()


class ClearMemoryRequest(BaseModel):
    confirm: bool = False


class MemoryCandidateInput(BaseModel):
    """Transport model kept independent from the optional memory package."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject: str = Field(default="user", min_length=1, max_length=128)
    predicate: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=2048)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class MemorySettingsInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    provider: str = Field(pattern="^(none|local|hindsight)$")
    database_path: str = Field(default="~/.openmimicry/memory/memory.sqlite3", max_length=2048)
    endpoint: str | None = Field(default=None, max_length=2048)
    retrieval_limit: int = Field(default=6, ge=0, le=50)
    retrieval_deadline_ms: int = Field(default=150, ge=25, le=5000)
    retention_days: int | None = Field(default=365, ge=1, le=36500)
    extraction_mode: str = Field(pattern="^(deterministic|llm)$")
    llm_backend: str | None = Field(default=None, max_length=64)


@router.get("/memory/settings")
async def memory_settings(request: Request) -> dict[str, object]:
    config = request.app.state.config.memory
    records = await request.app.state.memory.list(limit=1000) if config.enabled else []
    return {
        "enabled": config.enabled,
        "provider": config.provider,
        "database_path": config.database_path,
        "endpoint": config.endpoint,
        "extraction": config.extraction_mode,
        "llm_backend": config.llm_backend,
        "retrieval_limit": config.retrieval_limit,
        "retrieval_deadline_ms": config.retrieval_deadline_ms,
        "retention_days": config.retention_days,
        "store_raw_audio": False,
        "count": len(records),
        "restart_required_after_change": True,
    }


@router.post("/memory/settings")
async def update_memory_settings(
    values: MemorySettingsInput, request: Request
) -> dict[str, object]:
    if values.enabled and values.provider == "none":
        raise HTTPException(
            status_code=422,
            detail="Select Local SQLite or Hindsight before enabling long-term memory.",
        )
    if values.enabled and values.provider == "hindsight" and not values.endpoint:
        raise HTTPException(
            status_code=422,
            detail="A Hindsight endpoint is required when Hindsight memory is enabled.",
        )
    try:
        candidate = MemoryConfig.model_validate(
            {**values.model_dump(mode="json"), "store_raw_audio": False}
        )
    except ValidationError as exc:
        details = [
            {
                "location": list(error.get("loc", ())),
                "message": str(error.get("msg", "Invalid memory settings.")),
                "type": str(error.get("type", "value_error")),
            }
            for error in exc.errors(include_url=False, include_input=False)
        ]
        raise HTTPException(status_code=422, detail=details) from exc
    if candidate.llm_backend and candidate.llm_backend not in request.app.state.config.llm.backends:
        raise HTTPException(status_code=422, detail="memory LLM backend is not configured")
    persist_memory_settings(candidate.model_dump(mode="json"))
    result = candidate.model_dump(mode="json")
    result.update({"ok": True, "restart_required": True})
    return result


@router.get("/memory/records")
async def memory_records(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, object]:
    records = await request.app.state.memory.list(limit=limit)
    return {"records": [record.model_dump(mode="json") for record in records]}


@router.put("/memory/records/{memory_id}")
async def update_memory(
    memory_id: str,
    candidate: MemoryCandidateInput,
    request: Request,
) -> dict[str, object]:
    if len(memory_id) > 128:
        raise HTTPException(status_code=422, detail="invalid memory id")
    try:
        updated = await request.app.state.memory.update(memory_id, candidate)
    except NotImplementedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="memory record not found or conflicts")
    return {"updated": True, "id": memory_id}


@router.delete("/memory/records/{memory_id}")
async def delete_memory(memory_id: str, request: Request) -> dict[str, object]:
    if len(memory_id) > 128:
        raise HTTPException(status_code=422, detail="invalid memory id")
    try:
        deleted = await request.app.state.memory.delete(memory_id)
    except NotImplementedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="memory record not found")
    return {"deleted": True, "id": memory_id}


@router.post("/memory/clear")
async def clear_memory(values: ClearMemoryRequest, request: Request) -> dict[str, object]:
    if not values.confirm:
        raise HTTPException(status_code=422, detail="confirm=true is required")
    try:
        count = await request.app.state.memory.clear()
    except NotImplementedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"deleted": count}


@router.get("/memory/export")
async def export_memory(request: Request) -> JSONResponse:
    records = await request.app.state.memory.list(limit=1000)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return JSONResponse(
        {
            "schema_version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "records": [record.model_dump(mode="json") for record in records],
        },
        headers={
            "Content-Disposition": (f'attachment; filename="openmimicry-memory-{timestamp}.json"')
        },
    )
