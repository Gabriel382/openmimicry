"""``POST /mode/toggle`` — control continuous/wake input and agent voice.

Publishes a :class:`ConfigUpdated` event with the diff and applies the
matching :class:`SpeechController` method for the two keys it owns.
"""

from __future__ import annotations

import contextlib
import logging
import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from openmimicry.core import ConfigUpdated, EventBus, SpeechController
from pydantic import BaseModel, Field

from ..user_settings import persist_wake_names

__all__ = ["ModeToggleRequest", "WakeNameRequest", "router"]


_log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


ModeKey = Literal["continuous_listening", "live_wake", "agent_voice"]


class ModeToggleRequest(BaseModel):
    key: ModeKey
    value: bool


class WakeNameRequest(BaseModel):
    wake_name: str = Field(min_length=1, max_length=40)


router = APIRouter()


@router.get("/voice/settings")
async def voice_settings(request: Request) -> dict[str, object]:
    speech: SpeechController = request.app.state.wiring.speech
    names = list(getattr(speech, "wake_names", ["Mimi"]))
    mode_state = getattr(request.app.state, "mode_state", {})
    return {
        "wake_name": _primary_wake_name(names),
        "wake_names": names,
        "live_wake": bool(mode_state.get("live_wake", False)),
    }


@router.post("/voice/settings")
async def update_voice_settings(req: WakeNameRequest, request: Request) -> dict[str, object]:
    primary = _validate_wake_name(req.wake_name)
    names = [primary]
    if not primary.casefold().startswith("hey "):
        names.append(f"Hey {primary}")

    wiring = request.app.state.wiring
    speech: SpeechController = wiring.speech
    previous = list(getattr(speech, "wake_names", []))
    try:
        await speech.set_wake_names(names)  # type: ignore[attr-defined]
        persist_wake_names(names)
    except Exception as exc:
        if previous:
            with contextlib.suppress(Exception):
                await speech.set_wake_names(previous)  # type: ignore[attr-defined]
        _log.warning("wake-name update failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    mode_state = getattr(request.app.state, "mode_state", None)
    if isinstance(mode_state, dict):
        mode_state["wake_names"] = names
    wiring.bus.publish(ConfigUpdated(ts=_now(), diff={"wake_names": names}))
    return {"ok": True, "wake_name": primary, "wake_names": names}


@router.post("/mode/toggle")
async def mode_toggle(req: ModeToggleRequest, request: Request) -> dict[str, object]:
    wiring = request.app.state.wiring
    bus: EventBus = wiring.bus
    speech: SpeechController = wiring.speech

    try:
        if req.key == "continuous_listening":
            if req.value:
                await speech.enable_continuous_listening()
            else:
                await speech.disable_live_listening()
        elif req.key == "live_wake":
            if req.value:
                await speech.enable_live_listening(wake_names=None)
            else:
                await speech.disable_live_listening()
        elif req.key == "agent_voice":
            if not req.value:
                await speech.interrupt()
        else:  # pragma: no cover — Literal enforces this
            raise HTTPException(status_code=400, detail=f"unknown mode key: {req.key!r}")
    except HTTPException:
        raise
    except Exception as exc:
        _log.warning("mode_toggle apply failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    mode_state = getattr(request.app.state, "mode_state", None)
    if isinstance(mode_state, dict):
        mode_state[req.key] = req.value
        if req.value and req.key == "continuous_listening":
            mode_state["live_wake"] = False
        elif req.value and req.key == "live_wake":
            mode_state["continuous_listening"] = False
    bus.publish(ConfigUpdated(ts=_now(), diff={req.key: req.value}))
    return {"ok": True, "key": req.key, "value": req.value}


def _validate_wake_name(raw: str) -> str:
    name = " ".join(raw.split()).strip(" ,.:;!?-")
    if not name or not any(character.isalnum() for character in name):
        raise HTTPException(status_code=422, detail="wake name must contain a letter or number")
    if not re.fullmatch(r"[\wÀ-ÿ' -]+", name, flags=re.UNICODE):
        raise HTTPException(
            status_code=422,
            detail="wake name may contain letters, numbers, spaces, apostrophes, and hyphens",
        )
    return name


def _primary_wake_name(names: list[str]) -> str:
    for name in names:
        if not name.casefold().startswith("hey "):
            return name
    return names[0] if names else "Mimi"
