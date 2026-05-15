"""Schema-version migrations.

The current schema version is **1**. Migrations are looked up by
``(from_version, to_version)`` and chained when needed. Empty for now — v2
will register a callable here when the contract bumps.
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
