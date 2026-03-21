"""Typed data models for configuration and package resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RuntimeSettings:
    """Runtime settings consumed by the application at launch time."""

    app_name: str
    log_level: str
    backend_provider: str
    backend_endpoint: str
    model_name: str
    overlay_enabled: bool
    avatar_runtime: str
    profile: str = "basic"
    backend_options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AddonManifest:
    """Manifest describing a single installable package/add-on."""

    name: str
    version: str
    description: str
    category: str
    python_extra: str | None = None
    dependencies: list[str] = field(default_factory=list)
    runtime_enabled_by_default: bool = False


@dataclass(slots=True)
class ProfileDefinition:
    """Profile describing which packs and runtime settings are enabled."""

    name: str
    description: str
    packs: list[str]
    runtime_overrides: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ResolvedProfile:
    """A fully resolved profile after dependency expansion."""

    profile: ProfileDefinition
    manifests: list[AddonManifest]
    extras_to_install: list[str]
    merged_runtime_settings: dict[str, Any]
    profile_path: Path
