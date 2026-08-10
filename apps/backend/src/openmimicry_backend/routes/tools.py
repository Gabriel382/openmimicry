"""Optional provider-neutral tool settings and explicit execution endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from openmimicry.core.schemas.app import ToolsConfig
from pydantic import BaseModel, Field

from ..user_settings import persist_tools_settings

__all__ = ["router"]


router = APIRouter(prefix="/tools", tags=["tools"])


class ToolExecution(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)


@router.get("/settings")
async def settings(request: Request) -> dict[str, object]:
    return request.app.state.config.tools.model_dump(mode="json")


@router.post("/settings")
async def update_settings(values: ToolsConfig, request: Request) -> dict[str, object]:
    request.app.state.tool_service.reconfigure(values)
    current = request.app.state.config
    request.app.state.config = current.model_copy(update={"tools": values})
    persist_tools_settings(values.model_dump(mode="json"))
    return {"ok": True, **values.model_dump(mode="json")}


@router.post("/execute")
async def execute(values: ToolExecution, request: Request) -> dict[str, object]:
    try:
        reply = await request.app.state.tool_service.try_execute(values.text)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"handled": reply is not None, "reply": reply}
