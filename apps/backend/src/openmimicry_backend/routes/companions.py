"""Bounded whole-companion profile import, export, and activation."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from ..appearance import AppearanceConfig
from ..avatar_selection import runtime_for_pack_kind
from ..companion_state import tts_for_voice_profile
from ..user_settings import (
    persist_active_companion,
    persist_avatar_selection,
    persist_avatar_transform,
    persist_tts_clone,
    persist_voice_settings,
)
from ..voice_profiles import VoiceProfileError, VoiceProfileStore
from ..wiring import refresh_tts

__all__ = ["router"]


router = APIRouter()
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_MAX_COMPRESSED = 96 * 1024 * 1024
_MAX_EXPANDED = 320 * 1024 * 1024
_MAX_ENTRIES = 3000


def _safe_member(member: zipfile.ZipInfo) -> PurePosixPath:
    path = PurePosixPath(member.filename.replace("\\", "/"))
    mode = member.external_attr >> 16
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.parts[0].endswith(":")
        or stat.S_ISLNK(mode)
    ):
        raise ValueError(f"unsafe companion archive entry: {member.filename!r}")
    return path


def _archive_files(archive: zipfile.ZipFile) -> dict[PurePosixPath, bytes]:
    members = archive.infolist()
    if len(members) > _MAX_ENTRIES:
        raise ValueError("companion archive contains too many entries")
    if sum(item.file_size for item in members) > _MAX_EXPANDED:
        raise ValueError("expanded companion archive exceeds 320 MiB")
    files: dict[PurePosixPath, bytes] = {}
    for member in members:
        path = _safe_member(member)
        canonical = PurePosixPath(*(part.casefold() for part in path.parts))
        if member.is_dir():
            continue
        if canonical in files:
            raise ValueError("companion archive contains duplicate paths")
        files[canonical] = archive.read(member)
    return files


def _yaml(content: bytes, label: str) -> dict[str, Any]:
    try:
        value = yaml.safe_load(content.decode("utf-8")) or {}
    except Exception as exc:
        raise ValueError(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a YAML mapping")
    return value


def _personality_path() -> Path:
    configured = Path(
        os.environ.get("OPENMIMICRY_PERSONALITY_PATH", "~/.openmimicry/personality.yml")
    ).expanduser()
    return configured if configured.is_file() else Path("config/personality.yml")


def _threejs_pack_settings(config: Any, pack_id: str) -> tuple[dict[str, Any], dict[str, str]]:
    avatar = getattr(config, "avatar", None)
    runtimes = getattr(avatar, "runtimes", {}) if avatar is not None else {}
    runtime = dict(runtimes.get("threejs", {})) if isinstance(runtimes, dict) else {}
    transforms = runtime.get("transforms", {})
    aliases = runtime.get("animation_aliases", {})
    transform = dict(transforms.get(pack_id, {})) if isinstance(transforms, dict) else {}
    mapping = dict(aliases.get(pack_id, {})) if isinstance(aliases, dict) else {}
    return transform, {str(key): str(value) for key, value in mapping.items()}


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


@router.get("/companions")
async def companions(request: Request) -> dict[str, object]:
    root = Path(request.app.state.config.app.data_dir).expanduser() / "companions"
    values: list[dict[str, object]] = []
    if root.is_dir():
        for manifest in sorted(root.glob("*/companion.yaml")):
            try:
                values.append(_yaml(manifest.read_bytes(), "companion.yaml"))
            except ValueError:
                continue
    active = getattr(getattr(request.app.state.config, "companion", None), "active_id", None)
    return {"companions": values, "active_companion": active}


def _stored_companion_root(request: Request, companion_id: str) -> Path:
    if not _ID.fullmatch(companion_id):
        raise HTTPException(status_code=422, detail="invalid companion id")
    base = (Path(request.app.state.config.app.data_dir).expanduser() / "companions").resolve()
    root = (base / companion_id).resolve()
    if root.parent != base or not (root / "companion.yaml").is_file():
        raise HTTPException(status_code=404, detail="companion is not installed")
    return root


@router.get("/companions/stored/{companion_id}/export")
async def export_stored_companion(companion_id: str, request: Request) -> Response:
    root = _stored_companion_root(request, companion_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for candidate in sorted(root.rglob("*")):
            if candidate.is_file():
                archive.write(candidate, candidate.relative_to(root).as_posix())
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{companion_id}.omprofile.zip"'},
    )


@router.delete("/companions/stored/{companion_id}")
async def delete_companion(companion_id: str, request: Request) -> dict[str, object]:
    """Delete a private profile without unloading its currently active components."""

    import shutil

    root = _stored_companion_root(request, companion_id)
    active = request.app.state.config.companion.active_id == companion_id
    shutil.rmtree(root)
    if active:
        persist_active_companion(None)
        current = request.app.state.config
        request.app.state.config = current.model_copy(
            update={"companion": current.companion.model_copy(update={"active_id": None})}
        )
    return {"ok": True, "deleted": companion_id, "was_active": active}


@router.get("/companions/current/export")
async def export_current_companion(
    request: Request,
    companion_id: str = Query(min_length=1, max_length=64),
    name: str = Query(min_length=1, max_length=128),
    include_voice_reference: bool = Query(default=False),
) -> Response:
    companion_id = companion_id.strip().casefold()
    if not _ID.fullmatch(companion_id):
        raise HTTPException(status_code=422, detail="invalid companion id")
    try:
        pack_id = str(request.app.state.active_pack)
        pack_root = request.app.state.character_registry.resolve(pack_id)
        personality_path = _personality_path()
        personality = personality_path.read_bytes()
        personality_values = _yaml(personality, "personality.yaml")
        appearance = yaml.safe_dump(
            request.app.state.appearance.model_dump(mode="json"),
            sort_keys=False,
            allow_unicode=True,
        ).encode()
        config = request.app.state.config
        configured_voice = getattr(getattr(config, "voice", None), "active_profile", None)
        voice_id = getattr(request.app.state, "active_voice_profile", None) or configured_voice
        pack_summary = next(
            item for item in request.app.state.character_registry.list() if item["id"] == pack_id
        )
        runtime_name = runtime_for_pack_kind(str(pack_summary["kind"]))
        transform, aliases = _threejs_pack_settings(config, pack_id)
        animation_speed = float(getattr(getattr(config, "avatar", None), "animation_speed", 1.0))
        manifest: dict[str, Any] = {
            "schema_version": 2,
            "id": companion_id,
            "name": name.strip(),
            "assistant_name": str(personality_values.get("assistant_name") or name).strip(),
            "aliases": [str(item) for item in personality_values.get("aliases", [])],
            "avatar_pack": pack_id,
            "avatar_runtime": runtime_name,
            "voice_profile": voice_id,
            "contains_voice_reference": False,
        }
        payloads: dict[str, bytes] = {
            "personality/personality.yaml": personality,
            "appearance/appearance.yaml": appearance,
            "avatar/settings.yaml": yaml.safe_dump(
                {
                    "runtime": runtime_name,
                    "transform": transform,
                    "animation_speed": animation_speed,
                    "animation_aliases": aliases,
                },
                sort_keys=False,
                allow_unicode=True,
            ).encode(),
        }
        for candidate in sorted(pack_root.rglob("*")):
            if candidate.is_file():
                relative = candidate.relative_to(pack_root).as_posix()
                payloads[f"avatar/{pack_id}/{relative}"] = candidate.read_bytes()
        if voice_id:
            store = VoiceProfileStore(config.app.data_dir)
            active_companion = config.companion.active_id
            bundled_voice = (
                Path(config.app.data_dir).expanduser()
                / "companions"
                / str(active_companion)
                / "voice"
            )
            if active_companion and (bundled_voice / "profile.yaml").is_file():
                profile, directory = store.resolve_directory(bundled_voice)
            else:
                profile, directory = store.resolve(str(voice_id))
            exported = dict(profile)
            reference = profile.get("reference")
            if not include_voice_reference:
                exported["reference"] = None
            payloads["voice/profile.yaml"] = yaml.safe_dump(
                exported, sort_keys=False, allow_unicode=True
            ).encode()
            if include_voice_reference and isinstance(reference, str):
                payloads[f"voice/{reference}"] = (directory / reference).read_bytes()
                manifest["contains_voice_reference"] = True
        checksums = {
            path: hashlib.sha256(content).hexdigest() for path, content in payloads.items()
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "companion.yaml", yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True)
            )
            archive.writestr("checksums.json", json.dumps(checksums, indent=2))
            archive.writestr(
                "rights.json",
                json.dumps(
                    {
                        "status": "personal_only",
                        "notice": "Verify avatar, personality, and voice rights before sharing.",
                        "contains_biometric_material": bool(manifest["contains_voice_reference"]),
                    },
                    indent=2,
                ),
            )
            for path, content in payloads.items():
                archive.writestr(path, content)
    except (OSError, StopIteration, ValueError, VoiceProfileError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{companion_id}.omprofile.zip"'},
    )


@router.post("/companions/import", status_code=201)
async def import_companion(
    request: Request,
    filename: str = Query(max_length=255),
    confirm_voice_reference: bool = Query(default=False),
) -> dict[str, object]:
    content = await request.body()
    if not filename.casefold().endswith(".zip") or not content or len(content) > _MAX_COMPRESSED:
        raise HTTPException(status_code=422, detail="companion ZIP must be 1 byte to 96 MiB")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            files = _archive_files(archive)
        manifest = _yaml(files[PurePosixPath("companion.yaml")], "companion.yaml")
        if manifest.get("schema_version") not in {1, 2} or not _ID.fullmatch(
            str(manifest.get("id") or "")
        ):
            raise ValueError("invalid companion schema or id")
        companion_id = str(manifest["id"])
        checksums = json.loads(files[PurePosixPath("checksums.json")].decode("utf-8"))
        if not isinstance(checksums, dict):
            raise ValueError("checksums.json must be an object")
        for raw_path, digest in checksums.items():
            key = PurePosixPath(str(raw_path).casefold())
            if key not in files or hashlib.sha256(files[key]).hexdigest() != digest:
                raise ValueError(f"checksum mismatch: {raw_path}")
        if manifest.get("contains_voice_reference") and not confirm_voice_reference:
            raise ValueError("confirm biometric voice-reference import explicitly")
        root = Path(request.app.state.config.app.data_dir).expanduser() / "companions"
        destination = root / companion_id
        if destination.exists():
            raise ValueError(f"companion {companion_id!r} already exists")
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".companion-", dir=root) as temporary:
            staging = Path(temporary) / companion_id
            staging.mkdir()
            for path, payload in files.items():
                target = staging.joinpath(*path.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
            os.replace(staging, destination)
    except (KeyError, OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "companion": manifest, "activation_required": True}


@router.post("/companions/{companion_id}/activate")
async def activate_companion(companion_id: str, request: Request) -> dict[str, object]:
    """Activate every companion component, then persist the selector last.

    The TTS adapter is refreshed before ``companion.active_id`` is committed,
    so a failed voice load cannot leave the next launch pointing at a partially
    activated profile.
    """

    root = Path(request.app.state.config.app.data_dir).expanduser() / "companions" / companion_id
    try:
        manifest = _yaml((root / "companion.yaml").read_bytes(), "companion.yaml")
        pack_id = str(manifest["avatar_pack"])
        registry = request.app.state.character_registry
        try:
            pack_path = registry.resolve(pack_id)
        except ValueError:
            pack_root = root / "avatar" / pack_id
            if not pack_root.is_dir():
                raise ValueError(f"companion avatar pack {pack_id!r} is missing") from None
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                for candidate in pack_root.rglob("*"):
                    if candidate.is_file():
                        relative = candidate.relative_to(pack_root).as_posix()
                        archive.write(candidate, f"{pack_id}/{relative}")
            registry.install_zip(buffer.getvalue())
            pack_path = registry.resolve(pack_id)
        pack_summary = next(item for item in registry.list() if item["id"] == pack_id)
        runtime_name = runtime_for_pack_kind(str(pack_summary["kind"]))
        if runtime_name is None:
            raise ValueError(f"companion pack kind {pack_summary['kind']!r} is unsupported")

        current = request.app.state.config
        runtime_cfg = dict(current.avatar.runtimes.get(runtime_name, {}))
        avatar_settings_path = root / "avatar" / "settings.yaml"
        avatar_settings = (
            _yaml(avatar_settings_path.read_bytes(), "avatar settings")
            if avatar_settings_path.is_file()
            else {}
        )
        transform = avatar_settings.get("transform", {})
        aliases = avatar_settings.get("animation_aliases", {})
        if not isinstance(transform, dict) or not isinstance(aliases, dict):
            raise ValueError("avatar transform and animation_aliases must be mappings")
        animation_speed = float(
            avatar_settings.get("animation_speed", current.avatar.animation_speed)
        )
        if runtime_name == "threejs":
            transforms = dict(runtime_cfg.get("transforms", {}))
            transforms[pack_id] = dict(transform)
            alias_sets = dict(runtime_cfg.get("animation_aliases", {}))
            alias_sets[pack_id] = {str(key): str(value) for key, value in aliases.items()}
            runtime_cfg.update(
                {
                    "transforms": transforms,
                    "animation_aliases": alias_sets,
                    "animation_speed": animation_speed,
                }
            )
        runtimes = dict(current.avatar.runtimes)
        runtimes[runtime_name] = runtime_cfg
        avatar_config = current.avatar.model_copy(
            update={
                "pack": pack_id,
                "runtime": runtime_name,
                "animation_speed": animation_speed,
                "runtimes": runtimes,
            }
        )

        voice_id = manifest.get("voice_profile")
        voice_config = current.voice
        voice_profile: dict[str, Any] | None = None
        voice_directory: Path | None = None
        if isinstance(voice_id, str) and voice_id:
            store = VoiceProfileStore(current.app.data_dir)
            voice_manifest = root / "voice" / "profile.yaml"
            if voice_manifest.is_file():
                # A bundled companion voice is authoritative even when an
                # older global profile happens to reuse the same id.
                voice_profile, voice_directory = store.resolve_directory(voice_manifest.parent)
            else:
                voice_profile, voice_directory = store.resolve(voice_id)
            voice_config = current.voice.model_copy(
                update={
                    "tts": tts_for_voice_profile(current.voice.tts, voice_profile, voice_directory),
                    "active_profile": voice_id,
                }
            )

        personality = root / "personality" / "personality.yaml"
        personality_values = _yaml(personality.read_bytes(), "personality.yaml")
        assistant_name = str(
            personality_values.get("assistant_name") or manifest.get("name") or "OpenMimicry"
        ).strip()
        assistant_aliases = [
            str(value).strip()
            for value in personality_values.get("aliases", [])
            if isinstance(value, str) and value.strip()
        ]
        wake_names = [assistant_name]
        if not assistant_name.casefold().startswith("hey "):
            wake_names.append(f"Hey {assistant_name}")
        wake = voice_config.stt.wake.model_copy(
            update={"names": wake_names, "aliases": assistant_aliases}
        )
        voice_config = voice_config.model_copy(
            update={"stt": voice_config.stt.model_copy(update={"wake": wake})}
        )
        candidate = current.model_copy(update={"avatar": avatar_config, "voice": voice_config})
        wiring = request.app.state.wiring
        supervisor = request.app.state.supervisor
        await supervisor.set_runtime_state("refreshing", reason="companion_profile")
        try:
            if voice_profile is not None:
                await refresh_tts(wiring, candidate)
            await wiring.speech.set_wake_names(wake_names, assistant_aliases)
            factory = getattr(wiring, "runtime_factories", {}).get(runtime_name)
            if factory is None:
                raise ValueError(f"avatar runtime {runtime_name!r} is unavailable")
            orchestrator = wiring.orchestrator
            runtime = (
                orchestrator.runtime if orchestrator.runtime.name == runtime_name else factory()
            )
            await orchestrator.select_character(
                character_id=pack_id,
                runtime=runtime,
                runtime_name=runtime_name,
                character_config={"pack_path": str(pack_path), "runtime": runtime_cfg},
            )
            wiring.avatar_runtime = runtime
        finally:
            await supervisor.set_runtime_state("ready")

        personality_target = Path(
            os.environ.get("OPENMIMICRY_PERSONALITY_PATH", "~/.openmimicry/personality.yml")
        ).expanduser()
        _write_atomic(personality_target, personality.read_bytes())
        appearance_data = _yaml(
            (root / "appearance" / "appearance.yaml").read_bytes(), "appearance.yaml"
        )
        appearance = AppearanceConfig.model_validate(appearance_data)
        appearance_target = Path(
            os.environ.get("OPENMIMICRY_APPEARANCE_PATH", "~/.openmimicry/appearance.yml")
        ).expanduser()
        _write_atomic(
            appearance_target,
            yaml.safe_dump(appearance_data, sort_keys=False, allow_unicode=True).encode(),
        )

        # Persist only after all fallible adapter/runtime operations succeeded.
        persist_avatar_selection(pack=pack_id, runtime=runtime_name)
        persist_voice_settings(wake_names=wake_names, wake_aliases=assistant_aliases)
        if runtime_name == "threejs":
            persist_avatar_transform(
                pack_id,
                dict(transform),
                animation_speed=animation_speed,
                animation_aliases={str(key): str(value) for key, value in aliases.items()},
            )
        if voice_profile is not None and voice_directory is not None and isinstance(voice_id, str):
            reference = voice_profile.get("reference")
            persist_tts_clone(
                provider=str(voice_profile["provider"]),
                voice_id=str(voice_profile["voice_id"]),
                consent_record=str(voice_profile["consent_record"]),
                reference_path=(
                    str(voice_directory / reference) if isinstance(reference, str) else None
                ),
                profile_id=voice_id,
            )
        persist_active_companion(companion_id)

        companion_config = candidate.companion.model_copy(update={"active_id": companion_id})
        request.app.state.config = candidate.model_copy(update={"companion": companion_config})
        request.app.state.appearance = appearance
        request.app.state.active_pack = pack_id
        request.app.state.active_voice_profile = voice_id
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "ok": True,
        "active_companion": companion_id,
        "active_pack": pack_id,
        "active_runtime": runtime_name,
        "active_voice_profile": voice_id,
        "restart_required": False,
    }
