"""Logging setup and bus-tap unit tests."""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import logging
from datetime import datetime, timezone

import pytest
from openmimicry.core.bus import EventBus
from openmimicry.core.logging import (
    bus_tap_loop,
    configure_logging,
    get_logger,
    level_for_event,
)
from openmimicry.core.schemas.events import (
    ConfigUpdated,
    ErrorEvent,
    LLMReplyComplete,
    LLMTokenStreamed,
    TaskCompleted,
    TaskSubmitted,
    TTSChunkSpoken,
    TTSInterrupted,
    UserTextSubmitted,
    WakeDetected,
)
from openmimicry.core.schemas.tasks import TaskHandle, TaskResult


def _ts() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def _reset_logging():
    """Force-reconfigure logging between tests so the singleton flag doesn't leak."""
    yield
    # No teardown needed — every test that needs config calls force=True.


def test_level_mapping() -> None:
    h = TaskHandle(id="t", runtime="mock")
    assert level_for_event(ErrorEvent(ts=_ts(), where="x", message="m")) == logging.ERROR
    assert level_for_event(TaskSubmitted(ts=_ts(), handle=h, summary="s")) == logging.INFO
    assert (
        level_for_event(
            TaskCompleted(ts=_ts(), handle=h, result=TaskResult(handle=h, status="succeeded"))
        )
        == logging.INFO
    )
    assert level_for_event(WakeDetected(ts=_ts(), name="Mimi")) == logging.INFO
    assert level_for_event(LLMReplyComplete(ts=_ts(), full_text="x")) == logging.INFO
    assert level_for_event(TTSInterrupted(ts=_ts())) == logging.INFO
    assert level_for_event(ConfigUpdated(ts=_ts(), diff={})) == logging.INFO
    assert level_for_event(TTSChunkSpoken(ts=_ts())) == logging.DEBUG
    assert level_for_event(LLMTokenStreamed(ts=_ts(), delta="x")) == logging.DEBUG
    assert level_for_event(UserTextSubmitted(ts=_ts(), text="x")) == logging.DEBUG


def test_configure_logging_json_is_parsable() -> None:
    buf = io.StringIO()
    configure_logging(level="DEBUG", format="json", stream=buf, force=True)
    log = get_logger("test")
    log.info("hello", extra_key="value")
    raw = buf.getvalue().splitlines()[-1]
    payload = json.loads(raw)
    assert payload["event"] == "hello"
    assert payload["extra_key"] == "value"
    assert payload["level"] == "info"
    assert "pid" in payload
    assert "app_version" in payload


def test_configure_logging_text_format_does_not_crash() -> None:
    buf = io.StringIO()
    configure_logging(level="INFO", format="text", stream=buf, force=True)
    log = get_logger("test")
    log.info("hello")
    out = buf.getvalue()
    assert "hello" in out


def test_configure_logging_invalid_level_raises() -> None:
    with pytest.raises(ValueError):
        configure_logging(level="NOPE", force=True)


async def test_bus_tap_emits_log_records() -> None:
    buf = io.StringIO()
    configure_logging(level="DEBUG", format="json", stream=buf, force=True)
    bus = EventBus()

    tap = asyncio.create_task(bus_tap_loop(bus))
    await asyncio.sleep(0)
    bus.publish(ErrorEvent(ts=_ts(), where="llm", message="boom"))
    bus.publish(TTSChunkSpoken(ts=_ts()))
    await asyncio.sleep(0.05)
    await bus.aclose()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await asyncio.wait_for(tap, timeout=0.5)

    lines = [line for line in buf.getvalue().splitlines() if line.strip()]
    parsed = [json.loads(line) for line in lines]
    # Find one error and at least one debug-level record for tts_chunk.
    assert any(r.get("level") == "error" and r.get("kind") == "error" for r in parsed)
    assert any(r.get("kind") == "tts_chunk" for r in parsed)
