"""AppConfig loader: YAML + profile overlay + env override + Pydantic validate.

The resolution order is the one documented in ``docs/configuration.md`` §1:

1. Defaults from the Pydantic schema.
2. Active config file (``--config`` flag, ``OPENMIMICRY_CONFIG``,
   ``./config/app.yaml``, ``~/.config/openmimicry/app.yaml``).
3. Profile overlay if ``OPENMIMICRY_PROFILE`` is set
   (``./config/profiles/<name>.yaml``).
4. Environment variables ``OPENMIMICRY__<SECTION>__<KEY>=...`` applied last.

Booleans accept ``true/false/1/0/yes/no``. Lists accept JSON syntax.
Secrets are not read from YAML; the API-key env var is referenced by name
(``api_key_env: OPENROUTER_API_KEY``) and the adapter reads it at startup.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping, MutableMapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ..schemas.app import SCHEMA_VERSION, AppConfig
from .migrations import migrate

__all__ = [
    "ConfigError",
    "SchemaVersionError",
    "diff_dicts",
    "load",
    "resolve_config_path",
]

ENV_PREFIX = "OPENMIMICRY__"
"""Prefix for env-var overrides. Double-underscore separates nesting levels."""

CONFIG_ENV_VAR = "OPENMIMICRY_CONFIG"
PROFILE_ENV_VAR = "OPENMIMICRY_PROFILE"

_TRUE_STRS = frozenset({"true", "1", "yes", "on"})
_FALSE_STRS = frozenset({"false", "0", "no", "off"})


class ConfigError(Exception):
    """Generic loader error with a ``where`` hint pointing at the offender."""

    def __init__(self, message: str, *, where: str | None = None) -> None:
        super().__init__(message)
        self.where = where

    def __str__(self) -> str:  # pragma: no cover — display only.
        base = super().__str__()
        return f"{base} (at {self.where})" if self.where else base


class SchemaVersionError(ConfigError):
    """Raised when the YAML's ``schema_version`` exceeds what we understand."""


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_config_path(explicit: str | os.PathLike[str] | None = None) -> Path | None:
    """Find the active config file according to the documented order.

    Returns ``None`` when no candidate exists; the loader then falls back to
    the schema defaults plus env overrides.
    """
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(os.path.expanduser(str(explicit))))
    env_path = os.environ.get(CONFIG_ENV_VAR)
    if env_path:
        candidates.append(Path(os.path.expanduser(env_path)))
    candidates.append(Path.cwd() / "config" / "app.yaml")
    candidates.append(Path(os.path.expanduser("~/.config/openmimicry/app.yaml")))

    for c in candidates:
        if c.is_file():
            return c
    return None


def _resolve_profile_path(name: str) -> Path | None:
    candidate = Path.cwd() / "config" / "profiles" / f"{name}.yaml"
    return candidate if candidate.is_file() else None


# ---------------------------------------------------------------------------
# YAML reading + merging
# ---------------------------------------------------------------------------


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read config file: {exc}", where=str(path)) from exc
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML: {exc}", where=str(path)) from exc
    if not isinstance(data, dict):
        raise ConfigError("top-level YAML must be a mapping", where=str(path))
    return data


def _deep_merge(
    base: MutableMapping[str, Any], overlay: Mapping[str, Any]
) -> MutableMapping[str, Any]:
    """In-place deep merge of ``overlay`` into ``base``. Scalars/lists replace."""
    for key, val in overlay.items():
        cur = base.get(key)
        if isinstance(cur, MutableMapping) and isinstance(val, Mapping):
            _deep_merge(cur, val)
        else:
            base[key] = val
    return base


# ---------------------------------------------------------------------------
# Env-var overlay
# ---------------------------------------------------------------------------


def _coerce_scalar(raw: str) -> Any:
    """Convert an env-var string into the most natural Python value."""
    lowered = raw.strip().lower()
    if lowered in _TRUE_STRS:
        return True
    if lowered in _FALSE_STRS:
        return False
    # Number?
    try:
        if "." in raw or "e" in raw.lower():
            return float(raw)
        return int(raw)
    except ValueError:
        pass
    # JSON-ish (list / dict / quoted string)?
    stripped = raw.strip()
    if stripped and stripped[0] in '[{"':
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
    return raw


def _env_overrides(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Build a nested dict from ``OPENMIMICRY__SECTION__KEY=value`` env vars."""
    src = dict(env) if env is not None else dict(os.environ)
    out: dict[str, Any] = {}
    for key, raw in src.items():
        if not key.startswith(ENV_PREFIX):
            continue
        path = key[len(ENV_PREFIX) :].split("__")
        if not all(path):
            continue
        cursor: dict[str, Any] = out
        for part in path[:-1]:
            child = cursor.get(part.lower())
            if not isinstance(child, dict):
                child = {}
                cursor[part.lower()] = child
            cursor = child
        cursor[path[-1].lower()] = _coerce_scalar(raw)
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load(
    path: str | os.PathLike[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    profile: str | None = None,
    allow_migrate: bool = False,
) -> AppConfig:
    """Load and validate an ``AppConfig`` from disk + env.

    Parameters
    ----------
    path
        Optional explicit path (``--config`` CLI flag's value). If ``None``,
        the documented search order is used.
    env
        Optional environment-variable mapping for tests. Defaults to
        ``os.environ``.
    profile
        Optional profile name. If ``None``, the ``OPENMIMICRY_PROFILE`` env
        var is honoured.
    allow_migrate
        When True, an older ``schema_version`` is migrated via
        ``config.migrations``. When False, a mismatch raises.
    """
    src_env = dict(env) if env is not None else dict(os.environ)
    profile_name = profile if profile is not None else src_env.get(PROFILE_ENV_VAR)

    # 1. Defaults — built in by Pydantic when we validate.
    merged: dict[str, Any] = {}

    # 2. Active config file.
    resolved = resolve_config_path(path) if path is not None else resolve_config_path(None)
    if resolved is not None:
        _deep_merge(merged, _read_yaml(resolved))

    # 3. Profile overlay.
    if profile_name:
        profile_path = _resolve_profile_path(profile_name)
        if profile_path is None:
            raise ConfigError(
                f"profile '{profile_name}' not found under config/profiles/",
                where=PROFILE_ENV_VAR,
            )
        _deep_merge(merged, _read_yaml(profile_path))

    # 4. Env overrides (last wins).
    overrides = _env_overrides(src_env)
    if overrides:
        _deep_merge(merged, overrides)

    # 5. schema_version migration.
    declared = int(merged.get("schema_version", SCHEMA_VERSION))
    if declared > SCHEMA_VERSION:
        raise SchemaVersionError(
            f"config schema_version={declared} is newer than this release "
            f"(expected {SCHEMA_VERSION}). Upgrade openmimicry or downgrade the config.",
            where=str(resolved) if resolved else "<defaults>",
        )
    if declared < SCHEMA_VERSION:
        if not allow_migrate:
            raise SchemaVersionError(
                f"config schema_version={declared} predates this release "
                f"(expected {SCHEMA_VERSION}). Re-run with allow_migrate=True "
                f"(--allow-config-migrate at the CLI) to apply migrations.",
                where=str(resolved) if resolved else "<defaults>",
            )
        merged = migrate(merged, declared, SCHEMA_VERSION)
        merged["schema_version"] = SCHEMA_VERSION

    # 6. Validate.
    try:
        return AppConfig.model_validate(merged)
    except ValidationError as exc:
        raise ConfigError(
            "config failed validation:\n" + str(exc),
            where=str(resolved) if resolved else "<defaults>",
        ) from exc


# ---------------------------------------------------------------------------
# Diff helper — used by the reloader and the bus.
# ---------------------------------------------------------------------------


def diff_dicts(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """Return a nested dict containing only the leaves that changed.

    Sentinel ``None`` is used for removed keys. Pure / side-effect-free.
    """
    diff: dict[str, Any] = {}
    keys = set(before.keys()) | set(after.keys())
    for key in keys:
        a = before.get(key)
        b = after.get(key)
        if a == b:
            continue
        if isinstance(a, Mapping) and isinstance(b, Mapping):
            sub = diff_dicts(a, b)
            if sub:
                diff[key] = sub
        else:
            diff[key] = b
    return diff


def _ensure_iter(x: Iterable[Any] | None) -> Iterable[Any]:
    """Compat shim — kept for potential future use; unused at the moment."""
    return x or ()
