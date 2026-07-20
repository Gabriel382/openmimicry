"""Consent-gated local reference upload and paid voice-id configuration."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, SecretStr

from ..user_settings import persist_tts_clone

__all__ = ["router"]


_MAX_REFERENCE_BYTES = 20 * 1024 * 1024
router = APIRouter()


class RemoteVoiceRequest(BaseModel):
    provider: str = Field(pattern="^elevenlabs$")
    voice_id: str = Field(min_length=1, max_length=128)
    consent_record: str = Field(min_length=10, max_length=256)


class VoiceCredentialRequest(BaseModel):
    action: str = Field(pattern="^(set|clear)$")
    token: SecretStr | None = None


@router.get("/voice/clone/settings")
async def voice_clone_settings(request: Request) -> dict[str, object]:
    clone = request.app.state.config.voice.tts.clone
    tts = request.app.state.wiring.tts
    status_reader = getattr(tts, "credential_status", None)
    credentials = (
        status_reader() if callable(status_reader) else {"session": False, "environment": False}
    )
    return {
        "adapter": request.app.state.config.voice.tts.adapter,
        "provider": clone.provider if clone else None,
        "voice_id": clone.voice_id if clone else None,
        "reference_configured": bool(clone and clone.reference_path),
        "consent_configured": bool(clone and clone.consent_record),
        "credentials": credentials,
        "restart_required_after_change": True,
    }


@router.post("/voice/clone/reference", status_code=201)
async def upload_clone_reference(
    request: Request,
    filename: str = Query(max_length=255),
    consent_record: str = Query(min_length=10, max_length=256),
) -> dict[str, object]:
    audio = await request.body()
    if not audio or len(audio) > _MAX_REFERENCE_BYTES:
        raise HTTPException(status_code=422, detail="reference audio must be 1 byte to 20 MiB")
    extension = _audio_extension(audio, filename)
    root = Path(request.app.state.config.app.data_dir).expanduser() / "voices" / "references"
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"reference-{uuid4().hex}{extension}"
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(audio)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    try:
        persist_tts_clone(
            provider="chatterbox-local",
            voice_id="local-reference",
            consent_record=consent_record,
            reference_path=str(target),
        )
    except Exception:
        # Do not retain biometric material when its configuration transaction
        # fails. The file is deliberately created before the settings update so
        # a successful config can never point at a missing reference.
        target.unlink(missing_ok=True)
        raise
    return {
        "ok": True,
        "provider": "chatterbox-local",
        "reference_configured": True,
        "restart_required": True,
    }


@router.post("/voice/clone/remote")
async def configure_remote_clone(values: RemoteVoiceRequest) -> dict[str, object]:
    persist_tts_clone(
        provider=values.provider,
        voice_id=values.voice_id,
        consent_record=values.consent_record,
        reference_path=None,
    )
    return {
        "ok": True,
        "provider": values.provider,
        "voice_id": values.voice_id,
        "restart_required": True,
    }


@router.post("/voice/credentials")
async def update_voice_credentials(
    values: VoiceCredentialRequest, request: Request
) -> dict[str, object]:
    """Set or clear an ElevenLabs token in process memory only."""

    tts = request.app.state.wiring.tts
    if getattr(tts, "name", None) != "elevenlabs":
        raise HTTPException(
            status_code=409,
            detail="session voice credentials require the ElevenLabs adapter",
        )
    try:
        if values.action == "clear":
            clearer = getattr(tts, "clear_session_api_key", None)
            if not callable(clearer):
                raise ValueError("this TTS adapter cannot clear session credentials")
            clearer()
        else:
            if values.token is None:
                raise ValueError("token is required when action is 'set'")
            setter = getattr(tts, "set_session_api_key", None)
            if not callable(setter):
                raise ValueError("this TTS adapter cannot accept session credentials")
            setter(values.token.get_secret_value())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    status_reader = getattr(tts, "credential_status", None)
    credentials = (
        status_reader() if callable(status_reader) else {"session": False, "environment": False}
    )
    return {"ok": True, "provider": "elevenlabs", "credentials": credentials}


def _audio_extension(content: bytes, filename: str) -> str:
    lowered = filename.casefold()
    if content.startswith(b"RIFF") and content[8:12] == b"WAVE":
        return ".wav"
    if content.startswith(b"ID3") or content.startswith((b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
        return ".mp3"
    if lowered.endswith(".wav") or lowered.endswith(".mp3"):
        raise HTTPException(status_code=422, detail="audio signature does not match WAV/MP3")
    raise HTTPException(status_code=422, detail="reference must be a WAV or MP3 file")
