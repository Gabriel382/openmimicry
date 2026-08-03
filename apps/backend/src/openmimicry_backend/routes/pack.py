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
from openmimicry.core import AppConfig
from pydantic import BaseModel, Field, model_validator

from ..avatar_selection import runtime_for_pack_kind
from ..user_settings import persist_avatar_selection, persist_avatar_transform

__all__ = ["PackCreateRequest", "PackSwapRequest", "RuntimeSwapRequest", "router"]


_log = logging.getLogger(__name__)


class PackSwapRequest(BaseModel):
    pack: str


class RuntimeSwapRequest(BaseModel):
    runtime: str


class ModelTransform(BaseModel):
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: float = Field(default=1.0, ge=0.05, le=10.0)
    auto_fit: bool = True
    target_height: float = Field(default=0.72, ge=0.1, le=3.0)
    target_y: float = Field(default=1.3, ge=-3.0, le=5.0)


class AvatarVisualSettings(ModelTransform):
    animation_speed: float = Field(default=1.0, ge=0.1, le=4.0)


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
    values = request.app.state.character_registry.list()
    enriched = [
        {
            **value,
            "required_runtime": runtime_for_pack_kind(value["kind"]) or "unavailable",
        }
        for value in values
    ]
    return {
        "packs": enriched,
        "active_pack": request.app.state.active_pack,
        "active_runtime": request.app.state.wiring.orchestrator.runtime.name,
    }


@router.get("/avatar/settings")
async def avatar_settings(request: Request) -> dict[str, object]:
    pack_id = str(request.app.state.active_pack)
    pack = _pack_summary(request, pack_id)
    return {
        "pack": pack_id,
        "runtime": request.app.state.wiring.orchestrator.runtime.name,
        "required_runtime": runtime_for_pack_kind(pack["kind"]) or "unavailable",
        "transform": _threejs_transform(request.app.state.config, pack_id),
        "animation_speed": request.app.state.config.avatar.animation_speed,
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
    pack = _pack_summary(request, req.pack)
    required_runtime = runtime_for_pack_kind(pack["kind"]) or "unavailable"
    factory = getattr(wiring, "runtime_factories", {}).get(required_runtime)
    if factory is None:
        raise HTTPException(
            status_code=409,
            detail=(f"pack {req.pack!r} requires unavailable runtime {required_runtime!r}"),
        )
    runtime = orchestrator.runtime if orchestrator.runtime.name == required_runtime else factory()
    try:
        pack_path = request.app.state.character_registry.resolve(req.pack)
        runtime_cfg = dict(request.app.state.config.avatar.runtimes.get(required_runtime, {}))
        if required_runtime == "threejs":
            runtime_cfg["animation_speed"] = request.app.state.config.avatar.animation_speed
        await orchestrator.select_character(
            character_id=req.pack,
            runtime=runtime,
            runtime_name=required_runtime,
            character_config={
                "pack_path": str(pack_path),
                "runtime": runtime_cfg,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    wiring.avatar_runtime = runtime
    request.app.state.active_pack = req.pack
    current_config = request.app.state.config
    request.app.state.config = current_config.model_copy(
        update={
            "avatar": current_config.avatar.model_copy(
                update={"pack": req.pack, "runtime": required_runtime}
            )
        }
    )
    persist_avatar_selection(pack=req.pack, runtime=required_runtime)
    return {"ok": True, "pack": req.pack, "runtime": required_runtime}


@router.post("/runtime/swap")
async def runtime_swap(req: RuntimeSwapRequest, request: Request) -> dict[str, object]:
    wiring = request.app.state.wiring
    orchestrator = wiring.orchestrator
    # The orchestrator's swap_runtime expects a built adapter. Building one
    # requires concrete classes which only ``wiring.py`` may import. We
    # therefore expose a per-name factory side-channel on ``wiring`` (set
    # up in ``main.py`` so this file stays Protocol-only).
    active_pack = str(request.app.state.active_pack)
    pack = _pack_summary(request, active_pack)
    required_runtime = runtime_for_pack_kind(pack["kind"]) or "unavailable"
    if req.runtime != required_runtime:
        raise HTTPException(
            status_code=409,
            detail=(
                f"pack {active_pack!r} requires runtime {required_runtime!r}; "
                "selecting the character changes its runtime automatically"
            ),
        )
    factory = getattr(wiring, "runtime_factories", {}).get(req.runtime)
    if factory is None:
        raise HTTPException(
            status_code=400,
            detail=f"unknown runtime {req.runtime!r}; expected one of "
            f"{sorted(getattr(wiring, 'runtime_factories', {}))}",
        )
    # The requested runtime is already canonical for this pack.  Re-selecting
    # through the character endpoint is the only supported mutation path and
    # avoids loading a stale pack from the orchestrator's old config.
    if orchestrator.runtime.name != req.runtime:
        raise HTTPException(
            status_code=409,
            detail="re-select the active character to repair its runtime",
        )
    persist_avatar_selection(pack=active_pack, runtime=req.runtime)
    return {"ok": True, "runtime": req.runtime}


@router.post("/avatar/transform")
async def update_avatar_transform(
    values: AvatarVisualSettings,
    request: Request,
) -> dict[str, object]:
    pack_id = str(request.app.state.active_pack)
    pack = _pack_summary(request, pack_id)
    if runtime_for_pack_kind(pack["kind"]) != "threejs":
        raise HTTPException(
            status_code=409,
            detail="3D transforms are available only for VRM/glTF characters",
        )

    transform = values.model_dump(mode="json", exclude={"animation_speed"})
    current = request.app.state.config
    runtime_cfg = dict(current.avatar.runtimes.get("threejs", {}))
    runtime_cfg["animation_speed"] = values.animation_speed
    transforms = dict(runtime_cfg.get("transforms", {}))
    transforms[pack_id] = transform
    runtime_cfg["transforms"] = transforms
    runtimes = dict(current.avatar.runtimes)
    runtimes["threejs"] = runtime_cfg
    candidate = current.model_copy(
        update={
            "avatar": current.avatar.model_copy(
                update={
                    "runtimes": runtimes,
                    "animation_speed": values.animation_speed,
                }
            )
        }
    )

    try:
        pack_path = request.app.state.character_registry.resolve(pack_id)
        runtime = request.app.state.wiring.orchestrator.runtime
        await request.app.state.wiring.orchestrator.select_character(
            character_id=pack_id,
            runtime=runtime,
            runtime_name="threejs",
            character_config={
                "pack_path": str(pack_path),
                "runtime": runtime_cfg,
            },
        )
        persist_avatar_transform(
            pack_id,
            transform,
            animation_speed=values.animation_speed,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    request.app.state.config = candidate
    return {
        "ok": True,
        "pack": pack_id,
        "runtime": "threejs",
        "transform": transform,
        "animation_speed": values.animation_speed,
    }


def _pack_summary(request: Request, pack_id: str) -> dict[str, str]:
    for item in request.app.state.character_registry.list():
        if item["id"] == pack_id:
            return item
    raise HTTPException(status_code=404, detail=f"character pack {pack_id!r} is not installed")


def _threejs_transform(config: AppConfig, pack_id: str) -> dict[str, object]:
    runtime_cfg = dict(config.avatar.runtimes.get("threejs", {}))
    values = runtime_cfg.get("transforms", {}).get(pack_id, {})
    if not isinstance(values, dict):
        values = {}
    return ModelTransform.model_validate(values).model_dump(mode="json")
