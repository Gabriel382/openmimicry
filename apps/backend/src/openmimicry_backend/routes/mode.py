"""``POST /mode/toggle`` — flip ``live_wake`` / ``agent_voice``.

Publishes a :class:`ConfigUpdated` event with the diff and applies the
matching :class:`SpeechController` method for the two keys it owns.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from openmimicry.core import ConfigUpdated, EventBus, SpeechController
from pydantic import BaseModel

__all__ = ["ModeToggleRequest", "router"]


_log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


ModeKey = Literal["live_wake", "agent_voice"]


class ModeToggleRequest(BaseModel):
    key: ModeKey
    value: bool


router = APIRouter()


@router.post("/mode/toggle")
async def mode_toggle(req: ModeToggleRequest, request: Request) -> dict[str, object]:
    wiring = request.app.state.wiring
    bus: EventBus = wiring.bus
    speech: SpeechController = wiring.speech

    bus.publish(ConfigUpdated(ts=_now(), diff={req.key: req.value}))

    try:
        if req.key == "live_wake":
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
    except Exception as exc:  # noqa: BLE001
        _log.warning("mode_toggle apply failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"ok": True, "key": req.key, "value": req.value}
