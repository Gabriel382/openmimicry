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

from ..user_settings import persist_voice_settings

__all__ = ["ModeToggleRequest", "VoiceSettingsRequest", "WakeNameRequest", "router"]


_log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


ModeKey = Literal["continuous_listening", "live_wake", "agent_voice"]


class ModeToggleRequest(BaseModel):
    key: ModeKey
    value: bool


class VoiceSettingsRequest(BaseModel):
    wake_name: str | None = Field(default=None, min_length=1, max_length=40)
    wake_aliases: list[str] | None = Field(default=None, max_length=12)
    stt_model: (
        Literal[
            "tiny.en",
            "base.en",
            "small.en",
            "medium.en",
            "distil-large-v3",
            "large-v3",
        ]
        | None
    ) = None
    post_speech_silence_duration: float | None = Field(default=None, ge=0.2, le=3.0)


# Kept as an import-compatible alias for collaborators using the v1.3.1 name.
WakeNameRequest = VoiceSettingsRequest


router = APIRouter()


@router.get("/voice/settings")
async def voice_settings(request: Request) -> dict[str, object]:
    speech: SpeechController = request.app.state.wiring.speech
    names = list(getattr(speech, "wake_names", ["Mimi"]))
    mode_state = getattr(request.app.state, "mode_state", {})
    return {
        "wake_name": _primary_wake_name(names),
        "wake_names": names,
        "wake_aliases": list(getattr(speech, "wake_aliases", [])),
        "stt_model": str(getattr(speech, "stt_model", "medium.en")),
        "live_wake": bool(mode_state.get("live_wake", False)),
        "post_speech_silence_duration": float(getattr(speech, "post_speech_silence_duration", 1.0)),
    }


@router.post("/voice/settings")
async def update_voice_settings(req: VoiceSettingsRequest, request: Request) -> dict[str, object]:
    if (
        req.wake_name is None
        and req.wake_aliases is None
        and req.stt_model is None
        and req.post_speech_silence_duration is None
    ):
        raise HTTPException(status_code=422, detail="at least one voice setting is required")

    primary: str | None = None
    names: list[str] | None = None
    aliases: list[str] | None = None
    if req.wake_name is not None:
        primary = _validate_wake_name(req.wake_name)
        names = [primary]
        if not primary.casefold().startswith("hey "):
            names.append(f"Hey {primary}")
        aliases = (
            [_validate_wake_name(alias) for alias in req.wake_aliases]
            if req.wake_aliases is not None
            else (["Me me"] if primary.casefold() == "mimi" else [])
        )
    elif req.wake_aliases is not None:
        aliases = [_validate_wake_name(alias) for alias in req.wake_aliases]

    wiring = request.app.state.wiring
    speech: SpeechController = wiring.speech
    previous_names = list(getattr(speech, "wake_names", []))
    previous_aliases = list(getattr(speech, "wake_aliases", []))
    previous_model = str(getattr(speech, "stt_model", "medium.en"))
    previous_pause = float(getattr(speech, "post_speech_silence_duration", 1.0))
    try:
        if names is not None:
            await speech.set_wake_names(names, aliases)  # type: ignore[attr-defined]
        elif aliases is not None:
            await speech.set_wake_names(previous_names, aliases)  # type: ignore[attr-defined]
        if req.stt_model is not None:
            await speech.set_stt_model(req.stt_model)  # type: ignore[attr-defined]
        if req.post_speech_silence_duration is not None:
            await speech.set_post_speech_silence_duration(  # type: ignore[attr-defined]
                req.post_speech_silence_duration
            )
        persist_voice_settings(
            wake_names=names,
            wake_aliases=aliases,
            stt_model=req.stt_model,
            post_speech_silence_duration=req.post_speech_silence_duration,
        )
    except Exception as exc:
        if (names is not None or aliases is not None) and previous_names:
            with contextlib.suppress(Exception):
                await speech.set_wake_names(previous_names, previous_aliases)  # type: ignore[attr-defined]
        if req.stt_model is not None:
            with contextlib.suppress(Exception):
                await speech.set_stt_model(previous_model)  # type: ignore[attr-defined]
        if req.post_speech_silence_duration is not None:
            with contextlib.suppress(Exception):
                await speech.set_post_speech_silence_duration(previous_pause)  # type: ignore[attr-defined]
        _log.warning("voice settings update failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    mode_state = getattr(request.app.state, "mode_state", None)
    if isinstance(mode_state, dict):
        if names is not None:
            mode_state["wake_names"] = names
            mode_state["wake_aliases"] = aliases or []
        if req.stt_model is not None:
            mode_state["stt_model"] = req.stt_model
        if req.post_speech_silence_duration is not None:
            mode_state["post_speech_silence_duration"] = req.post_speech_silence_duration

    # Preserve the API's primary-name-first order even though the controller
    # internally sorts longest prefixes first for correct wake matching.
    current_names = (
        list(names) if names is not None else list(getattr(speech, "wake_names", ["Mimi"]))
    )
    current_pause = float(getattr(speech, "post_speech_silence_duration", 1.0))
    current_aliases = list(getattr(speech, "wake_aliases", []))
    current_model = str(getattr(speech, "stt_model", "medium.en"))
    diff: dict[str, object] = {}
    if names is not None:
        diff["wake_names"] = current_names
    if aliases is not None:
        diff["wake_aliases"] = current_aliases
    if req.stt_model is not None:
        diff["stt_model"] = current_model
    if req.post_speech_silence_duration is not None:
        diff["post_speech_silence_duration"] = current_pause
    wiring.bus.publish(ConfigUpdated(ts=_now(), diff=diff))
    return {
        "ok": True,
        "wake_name": _primary_wake_name(current_names),
        "wake_names": current_names,
        "wake_aliases": current_aliases,
        "stt_model": current_model,
        "post_speech_silence_duration": current_pause,
    }


@router.post("/mode/toggle")
async def mode_toggle(req: ModeToggleRequest, request: Request) -> dict[str, object]:
    wiring = request.app.state.wiring
    bus: EventBus = wiring.bus
    speech: SpeechController = wiring.speech
    mode_state = getattr(request.app.state, "mode_state", None)
    previous_value = mode_state.get(req.key) if isinstance(mode_state, dict) else None
    if (
        isinstance(mode_state, dict)
        and req.key in {"continuous_listening", "live_wake"}
        and not req.value
    ):
        # Close the admission gate before the recorder finishes shutting down.
        mode_state[req.key] = False

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
        if isinstance(mode_state, dict) and previous_value is not None:
            mode_state[req.key] = previous_value
        _log.warning("mode_toggle apply failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

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
