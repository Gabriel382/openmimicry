"""Bounded whole-companion profile import and export."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import stat
import tempfile
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath

import yaml
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from ..appearance import AppearanceConfig
from ..user_settings import persist_avatar_pack, persist_tts_clone
from ..voice_profiles import VoiceProfileError, VoiceProfileStore

__all__ = ["router"]


router = APIRouter()
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_MAX_COMPRESSED = 96 * 1024 * 1024
_MAX_EXPANDED = 320 * 1024 * 1024
_MAX_ENTRIES = 3000


def _canonical_id(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9_-]+", "-", normalized.casefold())
    slug = re.sub(r"[-_]{2,}", "-", slug).strip("-_")[:64]
    if not slug:
        raise ValueError("companion id must contain a letter or number")
    return slug


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


def _yaml(content: bytes, label: str) -> dict[str, object]:
    try:
        value = yaml.safe_load(content.decode("utf-8")) or {}
    except Exception as exc:
        raise ValueError(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a YAML mapping")
    return value


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
    return {"companions": values}


@router.get("/companions/current/export")
async def export_current_companion(
    request: Request,
    companion_id: str = Query(min_length=1, max_length=64),
    name: str = Query(min_length=1, max_length=128),
    include_voice_reference: bool = Query(default=False),
) -> Response:
    try:
        companion_id = _canonical_id(companion_id)
        pack_id = str(request.app.state.active_pack)
        pack_root = request.app.state.character_registry.resolve(pack_id)
        personality_path = Path(
            os.environ.get("OPENMIMICRY_PERSONALITY_PATH", "~/.openmimicry/personality.yml")
        ).expanduser()
        if not personality_path.is_file():
            personality_path = Path("config/personality.yml")
        personality = personality_path.read_bytes()
        appearance = yaml.safe_dump(
            request.app.state.appearance.model_dump(mode="json"),
            sort_keys=False,
            allow_unicode=True,
        ).encode()
        voice_id = getattr(request.app.state, "active_voice_profile", None)
        manifest = {
            "schema_version": 1,
            "id": companion_id,
            "name": name.strip(),
            "avatar_pack": pack_id,
            "voice_profile": voice_id,
            "contains_voice_reference": False,
        }
        payloads: dict[str, bytes] = {
            "personality/personality.yaml": personality,
            "appearance/appearance.yaml": appearance,
        }
        for candidate in sorted(pack_root.rglob("*")):
            if candidate.is_file():
                payloads[f"avatar/{pack_id}/{candidate.relative_to(pack_root).as_posix()}"] = (
                    candidate.read_bytes()
                )
        if voice_id:
            profile, directory = VoiceProfileStore(request.app.state.config.app.data_dir).resolve(
                voice_id
            )
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
    except (OSError, ValueError, VoiceProfileError) as exc:
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
        if manifest.get("schema_version") != 1 or not _ID.fullmatch(str(manifest.get("id") or "")):
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
    root = Path(request.app.state.config.app.data_dir).expanduser() / "companions" / companion_id
    try:
        manifest = _yaml((root / "companion.yaml").read_bytes(), "companion.yaml")
        pack_id = str(manifest["avatar_pack"])
        try:
            pack_path = request.app.state.character_registry.resolve(pack_id)
        except ValueError:
            pack_root = root / "avatar" / pack_id
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                for candidate in pack_root.rglob("*"):
                    if candidate.is_file():
                        archive.write(candidate, f"{pack_id}/{candidate.relative_to(pack_root)}")
            request.app.state.character_registry.install_zip(buffer.getvalue())
            pack_path = request.app.state.character_registry.resolve(pack_id)
        runtime = request.app.state.wiring.orchestrator.runtime
        await runtime.load_character(pack_id, {"pack_path": str(pack_path)})
        request.app.state.active_pack = pack_id
        persist_avatar_pack(pack_id)
        personality = root / "personality" / "personality.yaml"
        personality_target = Path(
            os.environ.get("OPENMIMICRY_PERSONALITY_PATH", "~/.openmimicry/personality.yml")
        ).expanduser()
        personality_target.parent.mkdir(parents=True, exist_ok=True)
        personality_temporary = personality_target.with_suffix(personality_target.suffix + ".tmp")
        personality_temporary.write_bytes(personality.read_bytes())
        os.replace(personality_temporary, personality_target)
        appearance_data = _yaml(
            (root / "appearance" / "appearance.yaml").read_bytes(), "appearance.yaml"
        )
        request.app.state.appearance = AppearanceConfig.model_validate(appearance_data)
        appearance_target = Path(
            os.environ.get("OPENMIMICRY_APPEARANCE_PATH", "~/.openmimicry/appearance.yml")
        ).expanduser()
        appearance_target.parent.mkdir(parents=True, exist_ok=True)
        appearance_temporary = appearance_target.with_suffix(appearance_target.suffix + ".tmp")
        appearance_temporary.write_text(
            yaml.safe_dump(appearance_data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        os.replace(appearance_temporary, appearance_target)
        voice_manifest = root / "voice" / "profile.yaml"
        restart_required = True
        if voice_manifest.is_file():
            profile = _yaml(voice_manifest.read_bytes(), "voice profile")
            profile_id = str(profile["id"])
            store = VoiceProfileStore(request.app.state.config.app.data_dir)
            try:
                stored, directory = store.resolve(profile_id)
            except VoiceProfileError:
                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.write(voice_manifest, "profile.yaml")
                    reference = profile.get("reference")
                    if isinstance(reference, str):
                        archive.write(root / "voice" / reference, f"voice/{reference}")
                store.import_zip(buffer.getvalue(), confirm_reference=True)
                stored, directory = store.resolve(profile_id)
            reference = stored.get("reference")
            if stored["provider"] != "chatterbox-local" or isinstance(reference, str):
                persist_tts_clone(
                    provider=str(stored["provider"]),
                    voice_id=str(stored["voice_id"]),
                    consent_record=str(stored["consent_record"]),
                    reference_path=(
                        str(directory / reference) if isinstance(reference, str) else None
                    ),
                )
                request.app.state.active_voice_profile = profile_id
                restart_required = True
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "ok": True,
        "active_companion": companion_id,
        "active_pack": pack_id,
        "restart_required": restart_required,
    }
