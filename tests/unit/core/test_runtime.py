"""Runtime context-manager unit tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from openmimicry.core.runtime import Runtime, create_runtime
from openmimicry.core.schemas.app import AppConfig
from openmimicry.core.schemas.events import (
    LLMReplyComplete,
    TTSStarted,
    UserTextSubmitted,
)


def _ts() -> datetime:
    return datetime.now(timezone.utc)


async def test_runtime_starts_and_stops_cleanly() -> None:
    rt = Runtime(config=AppConfig())
    await rt.start()
    assert rt.started is True
    await rt.stop()
    assert rt.started is False


async def test_runtime_context_manager() -> None:
    async with Runtime(config=AppConfig()) as rt:
        assert rt.started is True
        assert rt.bus is not None
    assert rt.started is False


async def test_create_runtime_factory_yields_started_runtime() -> None:
    async with create_runtime(AppConfig()) as rt:
        assert rt.started is True


async def test_runtime_store_updates_on_published_events() -> None:
    async with Runtime(config=AppConfig()) as rt:
        rt.bus.publish(UserTextSubmitted(ts=_ts(), text="hello"))
        rt.bus.publish(LLMReplyComplete(ts=_ts(), full_text="hi back"))
        rt.bus.publish(TTSStarted(ts=_ts()))
        # Give the store-updater task a moment to consume.
        for _ in range(50):
            if rt.store.last_user_text == "hello" and rt.store.is_speaking:
                break
            await asyncio.sleep(0.01)
        assert rt.store.last_user_text == "hello"
        assert rt.store.last_assistant_text == "hi back"
        assert rt.store.is_speaking is True


async def test_runtime_double_start_is_idempotent() -> None:
    rt = Runtime(config=AppConfig())
    await rt.start()
    await rt.start()
    await rt.stop()


async def test_runtime_double_stop_is_idempotent() -> None:
    rt = Runtime(config=AppConfig())
    await rt.start()
    await rt.stop()
    await rt.stop()
