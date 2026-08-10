"""Edit the assistant system prompt without changing avatar output safety rules."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..user_settings import persist_voice_settings

__all__ = ["router"]


router = APIRouter()


class PersonalityRequest(BaseModel):
    system_prompt: str = Field(min_length=1, max_length=20_000)
    name: str = Field(default="OpenMimicry", min_length=1, max_length=80)
    aliases: list[str] = Field(default_factory=list, max_length=12)


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
        "name": str(data.get("assistant_name") or "OpenMimicry"),
        "aliases": [
            str(item)
            for item in (data.get("aliases") or [])
            if isinstance(item, str) and item.strip()
        ],
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
async def update_personality(values: PersonalityRequest, request: Request) -> dict[str, object]:
    """Save identity and make it the sole live wake-name source."""

    primary = " ".join(values.name.split()).strip()
    aliases = list(
        dict.fromkeys(
            " ".join(alias.split()).strip()
            for alias in values.aliases
            if " ".join(alias.split()).strip()
        )
    )
    names = [primary]
    if not primary.casefold().startswith("hey "):
        names.append(f"Hey {primary}")
    speech = request.app.state.wiring.speech
    previous_names = list(getattr(speech, "wake_names", []))
    previous_aliases = list(getattr(speech, "wake_aliases", []))
    try:
        await speech.set_wake_names(names, aliases)
        data = _read()
        data["assistant_name"] = primary
        data["aliases"] = aliases
        data["system_prompt"] = values.system_prompt.strip()
        target = _path()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        os.replace(temporary, target)
        persist_voice_settings(wake_names=names, wake_aliases=aliases)
        current = request.app.state.config
        wake = current.voice.stt.wake.model_copy(update={"names": names, "aliases": aliases})
        stt = current.voice.stt.model_copy(update={"wake": wake})
        request.app.state.config = current.model_copy(
            update={"voice": current.voice.model_copy(update={"stt": stt})}
        )
        mode_state = getattr(request.app.state, "mode_state", None)
        if isinstance(mode_state, dict):
            mode_state["wake_names"] = names
            mode_state["wake_aliases"] = aliases
    except (OSError, ValueError, yaml.YAMLError, RuntimeError) as exc:
        if previous_names:
            with contextlib.suppress(Exception):
                await speech.set_wake_names(previous_names, previous_aliases)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {**(await personality_settings()), "wake_names": names, "wake_aliases": aliases}
