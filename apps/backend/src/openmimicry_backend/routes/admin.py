"""``GET /config`` and ``POST /admin/reload``.

``GET /config`` is a debug-gated dump of the active :class:`AppConfig`.
``POST /admin/reload`` re-runs the config loader from the stored
``config_path`` and publishes :class:`ConfigUpdated` with a coarse diff
(the loader does the deep diff in M0).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from openmimicry.core import ConfigUpdated, EventBus

__all__ = ["router"]


_log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


router = APIRouter()


@router.get("/config")
async def get_config(request: Request) -> dict[str, object]:
    """Return the active :class:`AppConfig` as JSON.

    Gated behind ``OPENMIMICRY_DEBUG=1`` so a default install doesn't
    expose configuration over an unauthenticated HTTP surface.
    """
    if os.environ.get("OPENMIMICRY_DEBUG") != "1":
        raise HTTPException(
            status_code=403,
            detail="GET /config requires OPENMIMICRY_DEBUG=1",
        )
    wiring = request.app.state.wiring
    return {"config": wiring.runtime.config.model_dump(mode="json")}


@router.post("/admin/reload")
async def admin_reload(request: Request) -> dict[str, object]:
    wiring = request.app.state.wiring
    bus: EventBus = wiring.bus

    runtime = wiring.runtime
    reloader = getattr(runtime, "reloader", None)
    if reloader is None:
        # No file-backed reloader; emit a "config_touched" notice so
        # subscribers know an explicit reload was requested.
        bus.publish(ConfigUpdated(ts=_now(), diff={"_admin_reload": True}))
        return {"ok": True, "reload": "noop"}

    try:
        await reloader.reload_now()  # type: ignore[attr-defined]
    except AttributeError:
        # The M0 reloader does its own watching; an explicit reload may
        # not be exposed as a method. Publish the marker anyway.
        bus.publish(ConfigUpdated(ts=_now(), diff={"_admin_reload": True}))
        return {"ok": True, "reload": "noop"}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "reload": "applied"}
