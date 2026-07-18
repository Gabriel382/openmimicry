"""Persist the small, non-secret settings edited from the local dashboard."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "persist_llm_backend",
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
