"""EventBus unit tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from openmimicry.core.bus import EventBus
from openmimicry.core.schemas.events import (
    LLMTokenStreamed,
    UserTextSubmitted,
)


def _ts() -> datetime:
    return datetime.now(timezone.utc)


async def test_publish_to_single_subscriber_preserves_order() -> None:
    bus = EventBus()
    sub = bus.subscribe()
    bus.publish(UserTextSubmitted(ts=_ts(), text="a"))
    bus.publish(UserTextSubmitted(ts=_ts(), text="b"))
    bus.publish(UserTextSubmitted(ts=_ts(), text="c"))

    async def reader() -> list:
        out: list = []
        async for event in sub:
            out.append(event)
            if len(out) == 3:
                return out
        return out

    out = await asyncio.wait_for(reader(), timeout=0.5)
    assert [e.text for e in out] == ["a", "b", "c"]
    await bus.aclose()


async def test_publish_fans_out_to_every_subscriber() -> None:
    bus = EventBus()
    s1 = bus.subscribe()
    s2 = bus.subscribe()
    bus.publish(UserTextSubmitted(ts=_ts(), text="x"))
    bus.publish(UserTextSubmitted(ts=_ts(), text="y"))

    async def reader(it):
        events = []
        async for event in it:
            events.append(event)
            if len(events) == 2:
                return events

    a = await asyncio.wait_for(reader(s1), timeout=0.5)
    b = await asyncio.wait_for(reader(s2), timeout=0.5)
    assert [e.text for e in a] == ["x", "y"]
    assert [e.text for e in b] == ["x", "y"]
    await bus.aclose()


async def test_aclose_releases_subscribers() -> None:
    bus = EventBus()
    sub = bus.subscribe()
    bus.publish(LLMTokenStreamed(ts=_ts(), delta="hi"))

    async def reader() -> int:
        count = 0
        async for _ in sub:
            count += 1
        return count

    task = asyncio.create_task(reader())
    await asyncio.sleep(0)
    await bus.aclose()
    result = await asyncio.wait_for(task, timeout=0.5)
    assert result == 1


async def test_aclose_is_idempotent() -> None:
    bus = EventBus()
    await bus.aclose()
    await bus.aclose()
    assert bus.closed


async def test_drop_oldest_on_overflow_logs_once(caplog: pytest.LogCaptureFixture) -> None:
    bus = EventBus(maxsize=2)
    sub = bus.subscribe()
    bus.publish(UserTextSubmitted(ts=_ts(), text="1"))
    bus.publish(UserTextSubmitted(ts=_ts(), text="2"))
    with caplog.at_level("WARNING", logger="openmimicry.core.bus"):
        bus.publish(UserTextSubmitted(ts=_ts(), text="3"))
        bus.publish(UserTextSubmitted(ts=_ts(), text="4"))
    warnings = [r for r in caplog.records if "fell behind" in r.getMessage()]
    assert len(warnings) == 1
    assert bus.subscriber_count == 1
    await bus.aclose()
    await sub.aclose()


async def test_publish_after_close_is_no_op() -> None:
    bus = EventBus()
    await bus.aclose()
    bus.publish(UserTextSubmitted(ts=_ts(), text="post-close"))


async def test_subscriber_count_tracks_lifecycle() -> None:
    bus = EventBus()
    assert bus.subscriber_count == 0
    sub = bus.subscribe()
    assert bus.subscriber_count == 1
    await bus.aclose()
    await sub.aclose()
    assert bus.subscriber_count == 0
