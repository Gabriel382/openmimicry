"""Startup rehydration for the last transactionally activated companion."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from openmimicry.core import AppConfig
from openmimicry.core.schemas.app import TTSConfigSection

from .avatar_selection import runtime_for_pack_kind
from .voice_profiles import VoiceProfileError, VoiceProfileStore

__all__ = ["rehydrate_active_companion", "tts_for_voice_profile"]


_log = logging.getLogger(__name__)


def _mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must be a YAML mapping")
    return value


def tts_for_voice_profile(
    current: TTSConfigSection,
    profile: dict[str, Any],
    directory: Path,
) -> TTSConfigSection:
    """Build one complete TTS config from a resolved named profile."""

    provider = str(profile["provider"])
    reference = profile.get("reference")
    reference_path = str(directory / reference) if isinstance(reference, str) else None
    values = {
        **current.model_dump(mode="json"),
        "adapter": provider,
        "engine": str(profile.get("engine") or provider),
        "voice": str(profile["voice_id"]),
        "readiness_timeout_s": 180.0 if provider == "chatterbox-local" else 45.0,
        "clone": {
            "provider": provider,
            "voice_id": str(profile["voice_id"]),
            "consent_record": str(profile["consent_record"]),
            "reference_path": reference_path,
            "store_reference_locally": provider == "chatterbox-local",
        },
    }
    if provider == "elevenlabs":
        values["endpoint"] = "https://api.elevenlabs.io"
        values["secret"] = {"source": "env", "name": "ELEVENLABS_API_KEY"}
    return TTSConfigSection.model_validate(values)


def rehydrate_active_companion(config: AppConfig, registry: Any) -> AppConfig:
    """Overlay the private active profile before adapters are constructed.

    The function is deliberately fail-safe: a deleted or damaged private
    profile logs a warning and leaves the already validated user config in
    place instead of reverting to a tracked default.
    """

    companion_id = config.companion.active_id
    if companion_id is None:
        return config
    root = Path(config.app.data_dir).expanduser() / "companions" / companion_id
    try:
        manifest = _mapping(root / "companion.yaml")
        pack_id = str(manifest["avatar_pack"])
        pack_path = registry.resolve(pack_id)
        summary = next(item for item in registry.list() if item["id"] == pack_id)
        runtime_name = runtime_for_pack_kind(summary["kind"])
        if runtime_name is None:
            raise ValueError(f"unsupported companion pack kind: {summary['kind']}")

        runtime_cfg = dict(config.avatar.runtimes.get(runtime_name, {}))
        runtime_cfg["pack_path"] = str(pack_path)
        if runtime_name == "threejs":
            runtime_cfg["animation_speed"] = config.avatar.animation_speed
        runtimes = dict(config.avatar.runtimes)
        runtimes[runtime_name] = runtime_cfg
        avatar = config.avatar.model_copy(
            update={"pack": pack_id, "runtime": runtime_name, "runtimes": runtimes}
        )

        voice = config.voice
        voice_id = manifest.get("voice_profile")
        if isinstance(voice_id, str) and voice_id:
            store = VoiceProfileStore(config.app.data_dir)
            bundled = root / "voice" / "profile.yaml"
            if bundled.is_file():
                profile, directory = store.resolve_directory(bundled.parent)
            else:
                profile, directory = store.resolve(voice_id)
            voice = voice.model_copy(
                update={
                    "tts": tts_for_voice_profile(config.voice.tts, profile, directory),
                    "active_profile": voice_id,
                }
            )

        _log.info(
            "Rehydrated active companion: id=%s pack=%s runtime=%s voice=%s",
            companion_id,
            pack_id,
            runtime_name,
            voice.active_profile,
        )
        return config.model_copy(update={"avatar": avatar, "voice": voice})
    except (KeyError, OSError, StopIteration, ValueError, VoiceProfileError) as exc:
        _log.warning("Active companion %r could not be rehydrated: %s", companion_id, exc)
        return config
