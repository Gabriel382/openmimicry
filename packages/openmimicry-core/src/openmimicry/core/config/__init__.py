"""Configuration loader, migrations, hot-reload — owned by M0.

Use ``load(path)`` for a one-shot read, and ``ConfigReloader`` (opt-in via
``app.config_watch``) for hot reload.
"""

from __future__ import annotations

from .loader import (
    ConfigError,
    SchemaVersionError,
    diff_dicts,
    load,
    resolve_config_path,
)
from .migrations import MigrationError, migrate, register_migration
from .reloader import ConfigReloader

__all__ = [
    "ConfigError",
    "ConfigReloader",
    "MigrationError",
    "SchemaVersionError",
    "diff_dicts",
    "load",
    "migrate",
    "register_migration",
    "resolve_config_path",
]
