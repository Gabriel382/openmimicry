"""Persist the small, non-secret settings edited from the local dashboard."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "persist_avatar_selection",
    "persist_avatar_transform",
    "persist_interaction_settings",
    "persist_llm_backend",
    "persist_llm_model",
    "persist_memory_settings",
    "persist_tts_clone",
    "persist_voice_settings",
    "persist_wake_names",
    "user_config_path",
]


def user_config_path() -> Path:
    """Return the dashboard-managed overlay path."""

    configured = os.environ.get("OPENMIMICRY_USER_CONFIG")
    return Path(configured).expanduser() if configured else Path.cwd() / "config" / "user.yaml"


def persist_voice_settings(
    *,
    wake_names: list[str] | None = None,
    wake_aliases: list[str] | None = None,
    stt_model: str | None = None,
    post_speech_silence_duration: float | None = None,
    path: Path | None = None,
) -> Path:
    """Atomically update dashboard-managed voice settings.

    ``None`` means "leave this value unchanged", which keeps this overlay
    additive and preserves settings owned by the checked-in profiles.
    """

    if (
        wake_names is None
        and wake_aliases is None
        and stt_model is None
        and post_speech_silence_duration is None
    ):
        raise ValueError("at least one voice setting is required")

    target = path or user_config_path()
    data: dict[str, Any] = {}
    if target.is_file():
        loaded = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"user settings must be a YAML mapping: {target}")
        data = loaded

    voice = data.setdefault("voice", {})
    if not isinstance(voice, dict):
        raise ValueError("user settings voice section must be a mapping")
    stt = voice.setdefault("stt", {})
    if not isinstance(stt, dict):
        raise ValueError("user settings voice.stt section must be a mapping")
    if wake_names is not None:
        wake = stt.setdefault("wake", {})
        if not isinstance(wake, dict):
            raise ValueError("user settings voice.stt.wake section must be a mapping")
        wake["names"] = list(wake_names)
    if wake_aliases is not None:
        wake = stt.setdefault("wake", {})
        if not isinstance(wake, dict):
            raise ValueError("user settings voice.stt.wake section must be a mapping")
        wake["aliases"] = list(wake_aliases)
    if stt_model is not None:
        stt["model"] = stt_model
        stt["realtime_model_type"] = stt_model
        stt["use_main_model_for_realtime"] = True
    if post_speech_silence_duration is not None:
        stt["post_speech_silence_duration"] = float(post_speech_silence_duration)

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    os.replace(temporary, target)
    return target


def persist_wake_names(names: list[str], path: Path | None = None) -> Path:
    """Compatibility wrapper for callers that only edit wake names."""

    return persist_voice_settings(wake_names=names, path=path)


def persist_llm_backend(name: str, path: Path | None = None) -> Path:
    """Atomically persist only the selected safe backend name."""

    target = path or user_config_path()
    data: dict[str, Any] = {}
    if target.is_file():
        loaded = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"user settings must be a YAML mapping: {target}")
        data = loaded
    llm = data.setdefault("llm", {})
    if not isinstance(llm, dict):
        raise ValueError("user settings llm section must be a mapping")
    llm["active_backend"] = name
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    os.replace(temporary, target)
    return target


def persist_llm_model(backend: str, model: str, path: Path | None = None) -> Path:
    """Persist a non-secret model choice under an existing backend name."""

    target = path or user_config_path()
    data = _read_user_mapping(target)
    llm = data.setdefault("llm", {})
    if not isinstance(llm, dict):
        raise ValueError("user settings llm section must be a mapping")
    backends = llm.setdefault("backends", {})
    if not isinstance(backends, dict):
        raise ValueError("user settings llm.backends section must be a mapping")
    entry = backends.setdefault(backend, {})
    if not isinstance(entry, dict):
        raise ValueError(f"user settings llm.backends.{backend} must be a mapping")
    entry["model"] = model
    return _write_user_mapping(target, data)


def persist_interaction_settings(values: dict[str, Any], path: Path | None = None) -> Path:
    """Persist validated response-presentation values only."""

    target = path or user_config_path()
    data = _read_user_mapping(target)
    interaction = data.setdefault("interaction", {})
    if not isinstance(interaction, dict):
        raise ValueError("user settings interaction section must be a mapping")
    interaction["response_presentation"] = dict(values)
    return _write_user_mapping(target, data)


def persist_memory_settings(values: dict[str, Any], path: Path | None = None) -> Path:
    """Persist validated, non-secret memory configuration."""

    target = path or user_config_path()
    data = _read_user_mapping(target)
    data["memory"] = dict(values)
    return _write_user_mapping(target, data)


def persist_tts_clone(
    *,
    provider: str,
    voice_id: str,
    consent_record: str,
    reference_path: str | None,
    profile_id: str | None = None,
    path: Path | None = None,
) -> Path:
    """Persist clone metadata and references, but never an API token."""

    target = path or user_config_path()
    data = _read_user_mapping(target)
    voice = data.setdefault("voice", {})
    if not isinstance(voice, dict):
        raise ValueError("user settings voice section must be a mapping")
    tts = voice.setdefault("tts", {})
    if not isinstance(tts, dict):
        raise ValueError("user settings voice.tts section must be a mapping")
    tts["adapter"] = "chatterbox-local" if provider == "chatterbox-local" else "elevenlabs"
    tts["engine"] = (
        "chatterbox-turbo" if provider == "chatterbox-local" else "eleven_multilingual_v2"
    )
    # Dashboard settings override the checked-in profile. Persist the provider's
    # bounded readiness window with the adapter so switching from Piper cannot
    # accidentally leave Chatterbox on Piper's 30-second cold-start deadline.
    tts["readiness_timeout_s"] = 180.0 if provider == "chatterbox-local" else 45.0
    if provider == "elevenlabs":
        tts["endpoint"] = "https://api.elevenlabs.io"
        tts["secret"] = {"source": "env", "name": "ELEVENLABS_API_KEY"}
    tts["clone"] = {
        "provider": provider,
        "voice_id": voice_id,
        "consent_record": consent_record,
        "reference_path": reference_path,
        "store_reference_locally": provider == "chatterbox-local",
    }
    if profile_id is not None:
        voice["active_profile"] = profile_id
    return _write_user_mapping(target, data)


def persist_avatar_selection(
    *,
    pack: str | None = None,
    runtime: str | None = None,
    path: Path | None = None,
) -> Path:
    """Persist the last safe avatar selectors; local pack bytes stay private."""

    if pack is None and runtime is None:
        raise ValueError("pack or runtime is required")
    target = path or user_config_path()
    data = _read_user_mapping(target)
    avatar = data.setdefault("avatar", {})
    if not isinstance(avatar, dict):
        raise ValueError("user settings avatar section must be a mapping")
    if pack is not None:
        avatar["pack"] = pack
    if runtime is not None:
        avatar["runtime"] = runtime
    return _write_user_mapping(target, data)


def persist_avatar_transform(
    pack: str,
    values: dict[str, Any],
    *,
    animation_speed: float | None = None,
    path: Path | None = None,
) -> Path:
    """Persist a validated per-pack Three.js transform.

    Keeping transforms keyed by pack prevents settings for a human VRM from
    leaking into a mascot or a plain glTF model.  The dashboard never writes
    arbitrary runtime keys through this helper.
    """

    target = path or user_config_path()
    data = _read_user_mapping(target)
    avatar = data.setdefault("avatar", {})
    if not isinstance(avatar, dict):
        raise ValueError("user settings avatar section must be a mapping")
    if animation_speed is not None:
        avatar["animation_speed"] = float(animation_speed)
    runtimes = avatar.setdefault("runtimes", {})
    if not isinstance(runtimes, dict):
        raise ValueError("user settings avatar.runtimes section must be a mapping")
    threejs = runtimes.setdefault("threejs", {})
    if not isinstance(threejs, dict):
        raise ValueError("user settings avatar.runtimes.threejs must be a mapping")
    transforms = threejs.setdefault("transforms", {})
    if not isinstance(transforms, dict):
        raise ValueError("user settings avatar.runtimes.threejs.transforms must be a mapping")
    transforms[pack] = dict(values)
    return _write_user_mapping(target, data)


def _read_user_mapping(target: Path) -> dict[str, Any]:
    if not target.is_file():
        return {}
    loaded = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"user settings must be a YAML mapping: {target}")
    return loaded


def _write_user_mapping(target: Path, data: dict[str, Any]) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    os.replace(temporary, target)
    return target
