"""Persist the small, non-secret settings edited from the local dashboard."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

__all__ = ["persist_wake_names", "user_config_path"]


def user_config_path() -> Path:
    """Return the dashboard-managed overlay path."""

    configured = os.environ.get("OPENMIMICRY_USER_CONFIG")
    return Path(configured).expanduser() if configured else Path.cwd() / "config" / "user.yaml"


def persist_wake_names(names: list[str], path: Path | None = None) -> Path:
    """Atomically update ``voice.stt.wake.names`` without losing other settings."""

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
    wake = stt.setdefault("wake", {})
    if not isinstance(wake, dict):
        raise ValueError("user settings voice.stt.wake section must be a mapping")
    wake["names"] = list(names)

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    os.replace(temporary, target)
    return target
