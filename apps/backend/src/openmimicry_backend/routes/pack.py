"""``POST /pack/swap`` and ``POST /runtime/swap``.

These delegate to ``AvatarOrchestrator.load_character`` (via the active
runtime) and ``AvatarOrchestrator.swap_runtime`` respectively. The pack
loader and concrete avatar runtimes live in the avatar package; the
backend touches them only through the orchestrator's Protocol surface.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

__all__ = ["PackSwapRequest", "RuntimeSwapRequest", "router"]


_log = logging.getLogger(__name__)


class PackSwapRequest(BaseModel):
    pack: str


class RuntimeSwapRequest(BaseModel):
    runtime: str


router = APIRouter()


@router.post("/pack/swap")
async def pack_swap(req: PackSwapRequest, request: Request) -> dict[str, object]:
    wiring = request.app.state.wiring
    orchestrator = wiring.orchestrator
    runtime = wiring.avatar_runtime
    try:
        await runtime.load_character(req.pack, {})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Mirror the current directive so the new pack reflects state. The
    # orchestrator owns ``_current``; we ask it (best-effort, via getattr).
    current = getattr(orchestrator, "current", None)
    if current is not None:
        try:
            await runtime.apply_directive(current)
        except Exception as exc:  # noqa: BLE001
            _log.warning("re-apply current directive after pack swap: %s", exc)
    return {"ok": True, "pack": req.pack}


@router.post("/runtime/swap")
async def runtime_swap(req: RuntimeSwapRequest, request: Request) -> dict[str, object]:
    wiring = request.app.state.wiring
    orchestrator = wiring.orchestrator
    # The orchestrator's swap_runtime expects a built adapter. Building one
    # requires concrete classes which only ``wiring.py`` may import. We
    # therefore expose a per-name factory side-channel on ``wiring`` (set
    # up in ``main.py`` so this file stays Protocol-only).
    factory = getattr(wiring, "runtime_factories", {}).get(req.runtime)
    if factory is None:
        raise HTTPException(
            status_code=400,
            detail=f"unknown runtime {req.runtime!r}; expected one of "
            f"{sorted(getattr(wiring, 'runtime_factories', {}))}",
        )
    new_runtime = factory()
    try:
        await orchestrator.swap_runtime(new_runtime)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "runtime": req.runtime}
