"""Validation helpers for profiles, manifests, and runtime settings."""

from __future__ import annotations

from typing import Iterable


REQUIRED_RUNTIME_KEYS = {
    "app_name",
    "log_level",
    "backend_provider",
    "backend_endpoint",
    "model_name",
    "overlay_enabled",
    "avatar_runtime",
}

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}
VALID_PROFILES = {"basic", "extended", "studio", "full"}


class ConfigValidationError(ValueError):
    """Raised when config content is invalid."""


def require_keys(data: dict, required: Iterable[str], context: str) -> None:
    """Ensure required keys are present in a mapping."""

    missing = [key for key in required if key not in data]
    if missing:
        raise ConfigValidationError(f"Missing required keys in {context}: {', '.join(missing)}")


def validate_runtime_settings(data: dict) -> None:
    """Validate runtime settings data."""

    require_keys(data, REQUIRED_RUNTIME_KEYS, "runtime settings")

    log_level = str(data["log_level"]).upper()
    if log_level not in VALID_LOG_LEVELS:
        raise ConfigValidationError(
            f"Invalid log level '{data['log_level']}'. Expected one of: {sorted(VALID_LOG_LEVELS)}"
        )

    if not isinstance(data["overlay_enabled"], bool):
        raise ConfigValidationError("'overlay_enabled' must be a boolean")

    if not str(data["backend_provider"]).strip():
        raise ConfigValidationError("'backend_provider' cannot be empty")

    if not str(data["avatar_runtime"]).strip():
        raise ConfigValidationError("'avatar_runtime' cannot be empty")


def validate_profile_definition(data: dict) -> None:
    """Validate a profile definition mapping."""

    require_keys(data, {"name", "description", "packs"}, "profile definition")

    if data["name"] not in VALID_PROFILES:
        raise ConfigValidationError(
            f"Invalid profile name '{data['name']}'. Expected one of: {sorted(VALID_PROFILES)}"
        )

    packs = data["packs"]
    if not isinstance(packs, list) or not all(isinstance(item, str) and item.strip() for item in packs):
        raise ConfigValidationError("'packs' must be a non-empty list of package names")


def validate_manifest(data: dict) -> None:
    """Validate a package manifest mapping."""

    require_keys(data, {"name", "version", "description", "category"}, "addon manifest")

    deps = data.get("dependencies", [])
    if deps and (not isinstance(deps, list) or not all(isinstance(dep, str) and dep.strip() for dep in deps)):
        raise ConfigValidationError("'dependencies' must be a list of non-empty strings")
