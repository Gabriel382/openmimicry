"""ConfigReloader unit tests.

We avoid filesystem races by injecting a custom ``loader`` callable. The
``watchfiles.awatch`` integration is exercised end-to-end in the integration
suite (M0 brief §"Test surface" — integration bucket).
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

import pytest
from openmimicry.core.bus import EventBus
from openmimicry.core.config.reloader import ConfigReloader
from openmimicry.core.schemas.app import AppConfig
from openmimicry.core.schemas.events import ConfigUpdated


async def test_reload_once_publishes_diff_when_changed(tmp_path: Path) -> None:
    path = tmp_path / "app.yaml"
    path.write_text("schema_version: 1\n", encoding="utf-8")

    bus = EventBus()
    current = AppConfig()
    new = current.model_copy(update={"app": current.app.model_copy(update={"log_level": "DEBUG"})})

    reloader = ConfigReloader(path, bus=bus, current=current, loader=lambda: new)

    sub = bus.subscribe()

    async def reader():
        async for event in sub:
            return event

    task = asyncio.create_task(reader())
    await asyncio.sleep(0)
    await reloader._reload_once()  # exercise the diff path directly
    event = await asyncio.wait_for(task, timeout=0.5)
    assert isinstance(event, ConfigUpdated)
    assert event.diff == {"app": {"log_level": "DEBUG"}}
    assert reloader.current == new
    await bus.aclose()


async def test_reload_once_skips_publish_when_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "app.yaml"
    path.write_text("schema_version: 1\n", encoding="utf-8")

    bus = EventBus()
    current = AppConfig()
    reloader = ConfigReloader(path, bus=bus, current=current, loader=lambda: current)

    sub = bus.subscribe()
    events: list = []

    async def reader():
        async for event in sub:
            events.append(event)

    task = asyncio.create_task(reader())
    await asyncio.sleep(0)
    await reloader._reload_once()
    await asyncio.sleep(0.05)
    assert events == []
    await bus.aclose()
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await task


async def test_reload_swallows_loader_errors(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "app.yaml"
    path.write_text("schema_version: 1\n", encoding="utf-8")

    bus = EventBus()
    current = AppConfig()

    def _explode() -> AppConfig:
        raise RuntimeError("YAML on fire")

    reloader = ConfigReloader(path, bus=bus, current=current, loader=_explode)
    with caplog.at_level("WARNING"):
        await reloader._reload_once()
    assert any("failed to reload" in r.getMessage() for r in caplog.records)
    assert reloader.current == current
    await bus.aclose()


async def test_start_stop_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "app.yaml"
    path.write_text("schema_version: 1\n", encoding="utf-8")
    bus = EventBus()
    reloader = ConfigReloader(path, bus=bus, current=AppConfig(), loader=lambda: AppConfig())
    await reloader.start()
    await reloader.start()  # second call is a no-op
    await reloader.stop()
    await reloader.stop()  # second call is a no-op
    await bus.aclose()
