"""Liveness, readiness, and per-component adapter health."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..supervisor import RuntimeSupervisor

__all__ = ["router"]


_log = logging.getLogger(__name__)
HEALTHCHECK_TIMEOUT_S: float = 2.0
router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    """Compatibility summary plus the authoritative runtime snapshot."""

    families, components = await _probe_components(request)
    from openmimicry.core.schemas.app import SCHEMA_VERSION

    supervisor: RuntimeSupervisor | None = getattr(request.app.state, "supervisor", None)
    runtime = supervisor.snapshot() if supervisor is not None else _fallback_runtime()
    return {
        "ok": all(ok for family in families.values() for ok in family.values()),
        "adapters": families,
        "components": components,
        "runtime": runtime,
        "schema_version": SCHEMA_VERSION,
    }


@router.get("/health/live", response_model=None)
async def live(request: Request) -> dict[str, Any] | JSONResponse:
    supervisor: RuntimeSupervisor | None = getattr(request.app.state, "supervisor", None)
    snapshot = supervisor.snapshot() if supervisor is not None else _fallback_runtime()
    is_live = snapshot["state"] not in {"stopped"}
    body = {"live": is_live, **snapshot}
    return body if is_live else JSONResponse(status_code=503, content=body)


@router.get("/health/ready", response_model=None)
async def ready(request: Request) -> dict[str, Any] | JSONResponse:
    """Return 200 only when typed conversation work can be admitted now."""

    supervisor: RuntimeSupervisor | None = getattr(request.app.state, "supervisor", None)
    runtime = supervisor.snapshot() if supervisor is not None else _fallback_runtime()
    families, components = await _probe_components(request, families={"llm"})
    llm_ready = bool(families.get("llm")) and all(families["llm"].values())
    can_accept = bool(runtime["ready"]) and llm_ready
    body = {
        "ready": can_accept,
        "reason": (
            None
            if can_accept
            else "turn_in_progress"
            if runtime.get("active_turn_id")
            else "llm_unavailable"
            if not llm_ready
            else f"runtime_{runtime['state']}"
        ),
        "runtime": runtime,
        "components": components,
    }
    return body if can_accept else JSONResponse(status_code=503, content=body)


@router.get("/health/components")
async def component_health(request: Request) -> dict[str, Any]:
    families, components = await _probe_components(request)
    return {"adapters": families, "components": components}


async def _probe_components(
    request: Request,
    *,
    families: set[str] | None = None,
) -> tuple[dict[str, dict[str, bool]], dict[str, dict[str, Any]]]:
    wiring = request.app.state.wiring
    supervisor: RuntimeSupervisor | None = getattr(request.app.state, "supervisor", None)
    probes: list[tuple[str, str, Any]] = []
    for family, adapters in wiring.adapters_by_family.items():
        if families is not None and family not in families:
            continue
        probes.extend((family, name, adapter) for name, adapter in adapters.items())

    results = await asyncio.gather(
        *(_safe_healthcheck(adapter) for _, _, adapter in probes),
    )
    family_map: dict[str, dict[str, bool]] = {}
    component_map: dict[str, dict[str, Any]] = {}
    for (family, name, adapter), healthy in zip(probes, results, strict=True):
        family_map.setdefault(family, {})[name] = healthy
        runtime_info = getattr(adapter, "runtime_info", {})
        actual_device = runtime_info.get("device") if isinstance(runtime_info, dict) else None
        if supervisor is not None:
            component = supervisor.update_component(
                family=family,
                adapter=name,
                healthy=healthy,
                required=family == "llm",
                actual_device=str(actual_device) if actual_device else None,
                last_error=None if healthy else "healthcheck failed",
            )
        else:
            component = {
                "component": f"{family}:{name}",
                "family": family,
                "adapter": name,
                "state": "healthy"
                if healthy
                else ("unavailable" if family == "llm" else "degraded"),
                "required": family == "llm",
                "actual_device": actual_device,
                "last_error": None if healthy else "healthcheck failed",
            }
        component_map[component["component"]] = component
    return family_map, component_map


async def _safe_healthcheck(adapter: Any) -> bool:
    fn = getattr(adapter, "healthcheck", None)
    if fn is None:
        return False
    try:
        result = await asyncio.wait_for(fn(), timeout=HEALTHCHECK_TIMEOUT_S)
    except TimeoutError:
        _log.warning("healthcheck timed out for adapter %r", getattr(adapter, "name", "?"))
        return False
    except Exception as exc:
        _log.warning(
            "healthcheck raised for adapter %r: %s",
            getattr(adapter, "name", "?"),
            exc,
        )
        return False
    return bool(result)


def _fallback_runtime() -> dict[str, Any]:
    # Integration embedders that construct routes without the production
    # lifespan retain the old ready behaviour.
    return {
        "instance_id": "unmanaged",
        "state": "ready",
        "ready": True,
        "reason": None,
        "active_turn_id": None,
        "active_turn_sequence": None,
        "active_turn_source": None,
    }
