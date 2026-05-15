"""Workspace-wide pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from openmimicry.core.bus import EventBus
from openmimicry.core.config import load
from openmimicry.core.schemas.app import AppConfig

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def event_bus() -> Iterator[EventBus]:
    """A fresh ``EventBus`` per test. Callers ``await bus.aclose()`` if needed."""
    bus = EventBus()
    try:
        yield bus
    finally:
        # aclose is async; tests that need cleanup do it themselves.
        pass


@pytest.fixture
def minimal_yaml(tmp_path: Path) -> Path:
    """Write the canonical minimal YAML fixture and return its path."""
    src = FIXTURES / "configs" / "minimal.yaml"
    dest = tmp_path / "app.yaml"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


@pytest.fixture
def app_config(minimal_yaml: Path, monkeypatch: pytest.MonkeyPatch) -> AppConfig:
    """Load the minimal YAML and return a parsed ``AppConfig``.

    Env is scrubbed so resolution is deterministic across machines.
    """
    for key in ("OPENMIMICRY_CONFIG", "OPENMIMICRY_PROFILE"):
        monkeypatch.delenv(key, raising=False)
    return load(minimal_yaml, env={})
