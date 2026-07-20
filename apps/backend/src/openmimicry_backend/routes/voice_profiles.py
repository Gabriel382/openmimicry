"""Named Voice Profile CRUD, activation, and portable archives."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..user_settings import persist_tts_clone
from ..voice_profiles import VoiceProfileError, VoiceProfileStore

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
    return {"profiles": _store(request).list(), "active_profile": active}


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
        persist_tts_clone(
            provider=str(profile["provider"]),
            voice_id=str(profile["voice_id"]),
            consent_record=str(profile["consent_record"]),
            reference_path=str(directory / reference) if isinstance(reference, str) else None,
        )
    except (VoiceProfileError, OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    request.app.state.active_voice_profile = profile_id
    return {
        "ok": True,
        "active_profile": profile_id,
        "restart_required": True,
        "message": "Voice selected. Restart the backend to load its provider safely.",
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
