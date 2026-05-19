"""``GET /health`` — best-effort adapter healthcheck.

Returns 200 with a per-family map. ``ok`` is ``True`` only when every
adapter healthchecks to ``True``. Individual healthchecks are awaited
with a per-adapter timeout so a hung adapter can't stall the whole
endpoint.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Request

__all__ = ["router"]


_log = logging.getLogger(__name__)


HEALTHCHECK_TIMEOUT_S: float = 2.0


router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    wiring = request.app.state.wiring
    families: dict[str, dict[str, bool]] = {}
    overall = True

    for family_name, adapters in wiring.adapters_by_family.items():
        family_map: dict[str, bool] = {}
        for name, adapter in adapters.items():
            ok = await _safe_healthcheck(adapter)
            family_map[name] = ok
            if not ok:
                overall = False
        families[family_name] = family_map

    from openmimicry.core.schemas.app import SCHEMA_VERSION

    return {
        "ok": overall,
        "adapters": families,
        "schema_version": SCHEMA_VERSION,
    }


async def _safe_healthcheck(adapter: Any) -> bool:
    fn = getattr(adapter, "healthcheck", None)
    if fn is None:
        return False
    try:
        result = await asyncio.wait_for(fn(), timeout=HEALTHCHECK_TIMEOUT_S)
    except asyncio.TimeoutError:
        _log.warning("healthcheck timed out for adapter %r", getattr(adapter, "name", "?"))
        return False
    except Exception as exc:  # noqa: BLE001
        _log.warning(
            "healthcheck raised for adapter %r: %s",
            getattr(adapter, "name", "?"),
            exc,
        )
        return False
    return bool(result)
