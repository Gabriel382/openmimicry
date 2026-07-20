"""Edit the assistant system prompt without changing avatar output safety rules."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

__all__ = ["router"]


router = APIRouter()


class PersonalityRequest(BaseModel):
    system_prompt: str = Field(min_length=1, max_length=20_000)


def _path() -> Path:
    return Path(
        os.environ.get("OPENMIMICRY_PERSONALITY_PATH", "~/.openmimicry/personality.yml")
    ).expanduser()


def _read() -> dict[str, Any]:
    candidate = _path()
    if not candidate.is_file():
        candidate = Path("config/personality.yml")
        if not candidate.is_file():
            return {}
    loaded = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError("personality document must be a YAML mapping")
    return loaded


@router.get("/personality/settings")
async def personality_settings() -> dict[str, object]:
    try:
        data = _read()
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "system_prompt": str(
            data.get("system_prompt") or "You are OpenMimicry, a helpful companion."
        ),
        "structured_avatar_output": bool(
            (data.get("behavior") or {}).get("structured_avatar_output", True)
            if isinstance(data.get("behavior"), dict)
            else True
        ),
    }


@router.post("/personality/settings")
async def update_personality(values: PersonalityRequest) -> dict[str, object]:
    try:
        data = _read()
        data["system_prompt"] = values.system_prompt.strip()
        target = _path()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        os.replace(temporary, target)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return await personality_settings()
