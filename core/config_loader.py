"""High-level config loader used by scripts and applications."""

from __future__ import annotations

import os
from pathlib import Path

from core.package_registry import PackageRegistry
from core.profile_resolver import ProfileResolver
from core.types import RuntimeSettings


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROFILES_DIR = PROJECT_ROOT / "profiles"
PACKS_DIR = PROJECT_ROOT / "packs"
REGISTRY_PATH = PACKS_DIR / "registry.json"
RUNTIME_DEFAULTS_PATH = PROJECT_ROOT / "apps" / "runtime.default.toml"


class ConfigLoader:
    """Loads and resolves project configuration."""

    def __init__(self) -> None:
        self.registry = PackageRegistry(REGISTRY_PATH)
        self.resolver = ProfileResolver(PROFILES_DIR, self.registry, RUNTIME_DEFAULTS_PATH)

    def load(self, profile_name: str | None = None) -> tuple[RuntimeSettings, list[str], list[str]]:
        """Load runtime settings and package info for a selected profile."""

        profile_name = profile_name or os.getenv("OPENMIMICRY_PROFILE", "basic")
        resolved = self.resolver.resolve(profile_name)

        settings = RuntimeSettings(
            app_name=resolved.merged_runtime_settings["app_name"],
            log_level=resolved.merged_runtime_settings["log_level"],
            backend_provider=resolved.merged_runtime_settings["backend_provider"],
            backend_endpoint=resolved.merged_runtime_settings["backend_endpoint"],
            model_name=resolved.merged_runtime_settings["model_name"],
            overlay_enabled=resolved.merged_runtime_settings["overlay_enabled"],
            avatar_runtime=resolved.merged_runtime_settings["avatar_runtime"],
            profile=resolved.merged_runtime_settings["profile"],
        )
        package_names = [manifest.name for manifest in resolved.manifests]
        extras = resolved.extras_to_install
        return settings, package_names, extras
