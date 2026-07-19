"""Schema-version migrations.

Migrations are pure, deterministic transformations. They never write the
source file; callers that choose to persist a migration must create a backup
and perform their own atomic replacement.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = [
    "MigrationError",
    "migrate",
    "register_migration",
]


MigrationFn = Callable[[dict[str, Any]], dict[str, Any]]


class MigrationError(Exception):
    """Raised when no migration path exists for the requested version bump."""


_REGISTRY: dict[tuple[int, int], MigrationFn] = {}


def register_migration(
    *, from_version: int, to_version: int
) -> Callable[[MigrationFn], MigrationFn]:
    """Decorator: register a migration from ``from_version`` to ``to_version``."""

    def _inner(fn: MigrationFn) -> MigrationFn:
        key = (from_version, to_version)
        if key in _REGISTRY:
            raise MigrationError(f"migration {from_version}->{to_version} already registered")
        _REGISTRY[key] = fn
        return fn

    return _inner


def migrate(data: dict[str, Any], from_version: int, to_version: int) -> dict[str, Any]:
    """Migrate ``data`` from ``from_version`` to ``to_version``.

    The v1 → v1 case is a no-op. Cross-version chains walk the registry by
    incrementing one major step at a time so we don't have to register the
    full cross-product of versions.
    """
    if from_version == to_version:
        return data
    if from_version > to_version:
        raise MigrationError(
            f"cannot downgrade config from schema_version={from_version} "
            f"to {to_version}; downgrades are not supported."
        )

    current = from_version
    current_data = dict(data)
    while current < to_version:
        step = (current, current + 1)
        fn = _REGISTRY.get(step)
        if fn is None:
            raise MigrationError(
                f"no migration registered for schema_version "
                f"{step[0]}->{step[1]}; you are running an older release."
            )
        current_data = fn(current_data)
        current += 1
    return current_data


@register_migration(from_version=1, to_version=2)
def _v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Add v1.6 optional sections without enabling new data processing."""

    migrated = dict(data)
    voice = migrated.get("voice") if isinstance(migrated.get("voice"), dict) else {}
    modes = voice.get("modes") if isinstance(voice.get("modes"), dict) else {}
    text_enabled = bool(modes.get("text_always_on", True))
    voice_enabled = bool(modes.get("agent_voice", True))
    if text_enabled and voice_enabled:
        mode = "parallel"
    elif text_enabled:
        mode = "text_only"
    else:
        mode = "voice_only" if voice_enabled else "text_only"

    migrated.setdefault(
        "interaction",
        {
            "response_presentation": {
                "mode": mode,
                "dismiss_policy": "after_both",
                "minimum_ms": 2500,
                "base_ms": 1500,
                "ms_per_character": 55,
                "maximum_ms": 30000,
                "allow_accessibility_captions": True,
            },
            "show_rejected_wake_transcripts": True,
            "restore_geometry": True,
        },
    )
    migrated.setdefault("memory", {"enabled": False, "provider": "none"})
    migrated.setdefault("distribution", {"profile": "commercial"})
    migrated["schema_version"] = 2
    return migrated
