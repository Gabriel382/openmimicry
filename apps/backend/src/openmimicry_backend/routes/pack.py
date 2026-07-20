"""``POST /pack/swap`` and ``POST /runtime/swap``.

These delegate to ``AvatarOrchestrator.load_character`` (via the active
runtime) and ``AvatarOrchestrator.swap_runtime`` respectively. The pack
loader and concrete avatar runtimes live in the avatar package; the
backend touches them only through the orchestrator's Protocol surface.
"""

from __future__ import annotations

import base64
import binascii
import io
import logging
import zipfile

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, model_validator

from ..user_settings import persist_avatar_pack

__all__ = ["PackCreateRequest", "PackSwapRequest", "RuntimeSwapRequest", "router"]


_log = logging.getLogger(__name__)


class PackSwapRequest(BaseModel):
    pack: str


class RuntimeSwapRequest(BaseModel):
    runtime: str


class PackCreateRequest(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    author: str = Field(min_length=1, max_length=128)
    license: str = Field(min_length=1, max_length=128)
    fps: int = Field(default=6, ge=1, le=60)
    sprites: dict[str, str]

    @model_validator(mode="after")
    def upload_is_bounded(self) -> PackCreateRequest:
        if not self.sprites or len(self.sprites) > 6:
            raise ValueError("provide 1-6 lifecycle sprites")
        if sum(len(value) for value in self.sprites.values()) > 64 * 1024 * 1024:
            raise ValueError("encoded character sprites exceed 64 MiB")
        return self


router = APIRouter()


@router.get("/static/characters/{pack_id}/{asset_path:path}", include_in_schema=False)
async def character_asset(pack_id: str, asset_path: str, request: Request) -> FileResponse:
    """Serve a validated asset from either the private or bundled pack root."""

    try:
        root = request.app.state.character_registry.resolve(pack_id).resolve()
        candidate = (root / asset_path).resolve()
        if root not in candidate.parents or not candidate.is_file():
            raise ValueError("character asset is missing or unsafe")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(candidate)


@router.get("/packs")
async def packs(request: Request) -> dict[str, object]:
    return {
        "packs": request.app.state.character_registry.list(),
        "active_pack": request.app.state.active_pack,
    }


@router.post("/pack/import", status_code=201)
async def pack_import(
    request: Request,
    filename: str = Query(default="character.zip", max_length=255),
) -> dict[str, object]:
    try:
        result = request.app.state.character_registry.install_zip(
            await request.body(), filename=filename
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "pack": result}


@router.post("/pack/create", status_code=201)
async def pack_create(values: PackCreateRequest, request: Request) -> dict[str, object]:
    decoded: dict[str, bytes] = {}
    try:
        for state, encoded in values.sprites.items():
            payload = encoded.split(",", 1)[1] if encoded.startswith("data:") else encoded
            decoded[state] = base64.b64decode(payload, validate=True)
        result = request.app.state.character_registry.create_sprite_pack(
            pack_id=values.id,
            name=values.name,
            author=values.author,
            license_name=values.license,
            sprites=decoded,
            fps=values.fps,
        )
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "pack": result}


@router.get("/pack/template")
async def pack_template() -> Response:
    """Return a tiny, valid, versioned Sprite2D pack tutorial ZIP."""

    transparent_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAF/gL+XjQ3WQAAAABJRU5ErkJggg=="
    )
    manifest = """schema_version: 1
id: my_character
name: My Character
author: Your Name
license: MIT
kind: sprite2d
preview: idle/000.png
default_state: idle
default_emotion: neutral
emotions:
  idle:
    frames: idle
    speaking_frames: speaking
    fps: 6
    loop: true
  listening:
    frames: listening
    speaking_frames: speaking
    fps: 6
    loop: true
  thinking:
    frames: thinking
    speaking_frames: speaking
    fps: 6
    loop: true
  speaking:
    frames: speaking
    speaking_frames: speaking
    fps: 8
    loop: true
  happy:
    frames: happy
    fps: 6
    loop: false
  error:
    frames: error
    fps: 6
    loop: false
"""
    readme = """OpenMimicry Sprite2D pack template (v1.6)

Replace each 000.png with a transparent-background sprite. Add numbered
frames (001.png, 002.png, ...) for animation. Keep exactly one pack.yaml.
Use an SPDX license identifier when possible and only include assets you own
or are allowed to redistribute. Then ZIP the my_character folder and import it
from the dashboard.
"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("my_character/pack.yaml", manifest)
        archive.writestr("my_character/README.txt", readme)
        for state in ("idle", "listening", "thinking", "speaking", "happy", "error"):
            archive.writestr(f"my_character/{state}/000.png", transparent_png)
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                'attachment; filename="openmimicry-character-template-v1.6.0.zip"'
            )
        },
    )


@router.post("/pack/swap")
async def pack_swap(req: PackSwapRequest, request: Request) -> dict[str, object]:
    wiring = request.app.state.wiring
    orchestrator = wiring.orchestrator
    runtime = orchestrator.runtime
    try:
        pack_path = request.app.state.character_registry.resolve(req.pack)
        await runtime.load_character(req.pack, {"pack_path": str(pack_path)})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Mirror the current directive so the new pack reflects state. The
    # orchestrator owns ``_current``; we ask it (best-effort, via getattr).
    current = getattr(orchestrator, "current", None)
    if current is not None:
        try:
            await runtime.apply_directive(current)
        except Exception as exc:
            _log.warning("re-apply current directive after pack swap: %s", exc)
    request.app.state.active_pack = req.pack
    try:
        persist_avatar_pack(req.pack)
    except (OSError, ValueError) as exc:
        _log.error("could not persist active avatar pack %r: %s", req.pack, exc)
        raise HTTPException(
            status_code=500,
            detail="The pack loaded, but its restart selection could not be saved.",
        ) from exc
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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    wiring.avatar_runtime = new_runtime
    return {"ok": True, "runtime": req.runtime}
