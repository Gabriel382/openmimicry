"""Runtime response-presentation and transactional language settings."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from openmimicry.core.schemas.app import LanguageConfig, ResponsePresentationConfig

from ..user_settings import persist_interaction_settings, persist_language_settings
from ..wiring import refresh_tts

__all__ = ["router"]


router = APIRouter()
_log = logging.getLogger(__name__)
_PIPER_VOICES = {
    "en": "en_US-lessac-medium",
    "fr": "fr_FR-siwis-medium",
    "es": "es_ES-davefx-medium",
    "pt-BR": "pt_BR-faber-medium",
}


@router.get("/interaction/settings")
async def interaction_settings(request: Request) -> dict[str, object]:
    current: ResponsePresentationConfig = request.app.state.presentation_state["value"]
    return current.model_dump(mode="json")


@router.post("/interaction/settings")
async def update_interaction_settings(
    values: ResponsePresentationConfig, request: Request
) -> dict[str, object]:
    request.app.state.presentation_state["value"] = values
    persist_interaction_settings(values.model_dump(mode="json"))

    appearance = request.app.state.appearance
    request.app.state.appearance = appearance.model_copy(
        update={
            "behaviour": appearance.behaviour.model_copy(
                update={
                    "bubble": appearance.behaviour.bubble.model_copy(
                        update={
                            "base_ms": values.base_ms,
                            "ms_per_character": values.ms_per_character,
                            "min_ms": values.minimum_ms,
                            "max_ms": values.maximum_ms,
                        }
                    )
                }
            )
        }
    )
    return values.model_dump(mode="json")


@router.get("/language/settings")
async def language_settings(request: Request) -> dict[str, object]:
    state = request.app.state.language_state
    value = state["value"]
    return {
        **value.model_dump(mode="json"),
        "status": state.get("status", "ready"),
        "detail": state.get("detail"),
        "target": state.get("target"),
        "stt_model": str(getattr(request.app.state.wiring.speech, "stt_model", "unknown")),
        "tts_voice": request.app.state.config.voice.tts.voice,
        "custom_voice_active": request.app.state.config.voice.active_profile is not None,
        "supported": ["auto", "en", "fr", "es", "pt-BR"],
    }


@router.post("/language/settings")
async def update_language_settings(values: LanguageConfig, request: Request) -> dict[str, object]:
    """Start a bounded atomic warm-up while the rest of the backend remains usable."""

    state = request.app.state.language_state
    task = state.get("task")
    if isinstance(task, asyncio.Task) and not task.done():
        raise HTTPException(status_code=409, detail="another language preparation is running")
    if values == state["value"] and state.get("status", "ready") == "ready":
        return await language_settings(request)
    state.update(
        {
            "status": "preparing",
            "detail": "Preparing speech recognition…",
            "target": values.model_dump(mode="json"),
        }
    )
    state["task"] = asyncio.create_task(
        _prepare_language(values, request.app), name="openmimicry.language.prepare"
    )
    return await language_settings(request)


async def _prepare_language(values: LanguageConfig, app: Any) -> None:
    state = app.state.language_state
    speech = app.state.wiring.speech
    current = app.state.config
    previous_model = str(getattr(speech, "stt_model", current.voice.stt.model))
    previous_stt_language = current.voice.stt.language
    target_model = previous_model
    stt_language = "pt" if values.input == "pt-BR" else values.input
    if stt_language != "en" and previous_model.endswith(".en"):
        target_model = "distil-large-v3"

    target_voice: str | None = None
    custom_voice = current.voice.active_profile is not None
    if (
        not custom_voice
        and current.voice.tts.adapter == "isolated-piper"
        and values.output in _PIPER_VOICES
    ):
        target_voice = _PIPER_VOICES[values.output]

    try:
        if target_model != previous_model:
            state["detail"] = f"Downloading/warming STT model {target_model} on first use…"
            await speech.set_stt_model(target_model)
        await speech.set_stt_language(stt_language)

        candidate_voice = current.voice
        if target_voice and target_voice != current.voice.tts.voice:
            state["detail"] = f"Downloading/warming {values.output} voice {target_voice}…"
            await _ensure_piper_voice(target_voice, current.voice.tts.data_dir)
            tts = current.voice.tts.model_copy(update={"voice": target_voice})
            candidate_voice = current.voice.model_copy(update={"tts": tts})

        stt = candidate_voice.stt.model_copy(
            update={
                "language": stt_language,
                "model": target_model,
                "realtime_model_type": target_model,
            }
        )
        candidate_voice = candidate_voice.model_copy(update={"stt": stt})
        candidate = current.model_copy(
            update={
                "interaction": current.interaction.model_copy(update={"language": values}),
                "voice": candidate_voice,
            }
        )
        if target_voice and target_voice != current.voice.tts.voice:
            await refresh_tts(app.state.wiring, candidate)
        persist_language_settings(
            input_language=values.input,
            output_language=values.output,
            tts_voice=target_voice,
        )
        app.state.config = candidate
        state["value"] = values
        state["status"] = "ready"
        state["detail"] = (
            "Language ready. The selected custom voice was retained; its multilingual quality "
            "depends on that voice provider."
            if custom_voice
            else "Language and matching standard voice are ready."
        )
        _log.info(
            "language settings committed: input=%s output=%s stt_model=%s tts_voice=%s",
            values.input,
            values.output,
            target_model,
            target_voice or current.voice.tts.voice,
        )
    except Exception as exc:
        with contextlib.suppress(Exception):
            await speech.set_stt_language(previous_stt_language)
        if target_model != previous_model:
            with contextlib.suppress(Exception):
                await speech.set_stt_model(previous_model)
        state["status"] = "error"
        state["detail"] = str(exc)
        _log.warning("language preparation failed: %s", exc, exc_info=True)
    finally:
        state["target"] = None


async def _ensure_piper_voice(voice: str, data_dir: str) -> None:
    root = Path(data_dir).expanduser()
    model = root / f"{voice}.onnx"
    config = Path(f"{model}.json")
    if model.is_file() and config.is_file():
        return
    root.mkdir(parents=True, exist_ok=True)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "piper.download_voices",
        "--data-dir",
        str(root),
        voice,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=600.0)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise RuntimeError(f"Piper voice download timed out: {voice}") from None
    if process.returncode != 0 or not model.is_file() or not config.is_file():
        detail = stderr.decode(errors="replace").strip() or stdout.decode(errors="replace").strip()
        raise RuntimeError(f"Piper voice download failed for {voice}: {detail[-1000:]}")
