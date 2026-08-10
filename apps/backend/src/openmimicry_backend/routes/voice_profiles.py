"""Named Voice Profile CRUD, activation, and portable archives."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..companion_state import tts_for_voice_profile
from ..user_settings import persist_active_companion, persist_tts_clone
from ..voice_profiles import VoiceProfileError, VoiceProfileStore
from ..wiring import refresh_tts

__all__ = ["router"]


router = APIRouter()


class RemoteProfileRequest(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    voice_id: str = Field(min_length=1, max_length=128)
    consent_record: str = Field(min_length=10, max_length=256)


def _store(request: Request) -> VoiceProfileStore:
    return VoiceProfileStore(request.app.state.config.app.data_dir)


@router.get("/voice/profiles")
async def list_voice_profiles(request: Request) -> dict[str, object]:
    active = getattr(request.app.state, "active_voice_profile", None)
    store = _store(request)
    profiles = store.list()
    if active and not any(item["id"] == active for item in profiles):
        companion_id = request.app.state.config.companion.active_id
        if companion_id:
            bundled = (
                Path(request.app.state.config.app.data_dir).expanduser()
                / "companions"
                / companion_id
                / "voice"
            )
            try:
                profile, directory = store.resolve_directory(bundled)
                profiles.append(store.public(profile, directory))
            except VoiceProfileError:
                pass
    return {"profiles": profiles, "active_profile": active}


@router.post("/voice/profiles/reference", status_code=201)
async def create_reference_profile(
    request: Request,
    profile_id: str = Query(min_length=1, max_length=64),
    name: str = Query(min_length=1, max_length=128),
    filename: str = Query(max_length=255),
    consent_record: str = Query(min_length=10, max_length=256),
) -> dict[str, object]:
    try:
        profile = _store(request).create_reference(
            profile_id=profile_id,
            name=name,
            filename=filename,
            consent_record=consent_record,
            audio=await request.body(),
        )
    except VoiceProfileError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "profile": profile}


@router.post("/voice/profiles/remote", status_code=201)
async def create_remote_profile(
    values: RemoteProfileRequest, request: Request
) -> dict[str, object]:
    try:
        profile = _store(request).create_remote(
            profile_id=values.id,
            name=values.name,
            voice_id=values.voice_id,
            consent_record=values.consent_record,
        )
    except VoiceProfileError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "profile": profile}


@router.post("/voice/profiles/import", status_code=201)
async def import_voice_profile(
    request: Request,
    confirm_reference: bool = Query(default=False),
) -> dict[str, object]:
    try:
        profile = _store(request).import_zip(
            await request.body(), confirm_reference=confirm_reference
        )
    except VoiceProfileError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "profile": profile}


@router.post("/voice/profiles/{profile_id}/activate")
async def activate_voice_profile(profile_id: str, request: Request) -> dict[str, object]:
    try:
        profile, directory = _store(request).resolve(profile_id)
        reference = profile.get("reference")
        current = request.app.state.config
        tts = tts_for_voice_profile(current.voice.tts, profile, directory)
        candidate = current.model_copy(
            update={
                "voice": current.voice.model_copy(
                    update={"tts": tts, "active_profile": profile_id}
                ),
                "companion": current.companion.model_copy(update={"active_id": None}),
            }
        )
        supervisor = request.app.state.supervisor
        await supervisor.set_runtime_state("refreshing", reason="voice_profile")
        try:
            await refresh_tts(request.app.state.wiring, candidate)
        finally:
            await supervisor.set_runtime_state("ready")
        persist_tts_clone(
            provider=str(profile["provider"]),
            voice_id=str(profile["voice_id"]),
            consent_record=str(profile["consent_record"]),
            reference_path=str(directory / reference) if isinstance(reference, str) else None,
            profile_id=profile_id,
        )
        persist_active_companion(None)
        request.app.state.config = candidate
    except (VoiceProfileError, OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    request.app.state.active_voice_profile = profile_id
    return {
        "ok": True,
        "active_profile": profile_id,
        "restart_required": False,
        "message": "Voice profile warmed and activated without a backend restart.",
    }


@router.get("/voice/profiles/{profile_id}/export")
async def export_voice_profile(
    profile_id: str,
    request: Request,
    include_reference: bool = Query(default=False),
) -> Response:
    try:
        content = _store(request).export(profile_id, include_reference=include_reference)
    except VoiceProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{profile_id}.voiceprofile.zip"'},
    )
