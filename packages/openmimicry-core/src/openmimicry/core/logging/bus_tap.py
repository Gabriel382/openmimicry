"""Bus tap — subscribes to the event bus and logs every event.

Level mapping (per M0 brief):

* ``ErrorEvent`` -> ERROR
* ``TaskSubmitted``, ``TaskCompleted``, ``WakeDetected``,
  ``LLMReplyComplete``, ``TTSInterrupted``, ``ConfigUpdated`` -> INFO
* everything else -> DEBUG

The tap is a long-running coroutine; it runs as a background task under
``Runtime`` and stops when the bus closes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..schemas.events import (
    ConfigUpdated,
    ErrorEvent,
    LLMReplyComplete,
    TaskCompleted,
    TaskSubmitted,
    TTSInterrupted,
    WakeDetected,
)
from .setup import get_logger

if TYPE_CHECKING:
    from ..bus import EventBus
    from ..schemas.events import RuntimeEvent

__all__ = ["bus_tap_loop", "level_for_event"]


_INFO_TYPES = (
    TaskSubmitted,
    TaskCompleted,
    WakeDetected,
    LLMReplyComplete,
    TTSInterrupted,
    ConfigUpdated,
)


def level_for_event(event: RuntimeEvent) -> int:
    """Resolve the log level for a single event."""
    if isinstance(event, ErrorEvent):
        return logging.ERROR
    if isinstance(event, _INFO_TYPES):
        return logging.INFO
    return logging.DEBUG


async def bus_tap_loop(bus: EventBus, *, subscription=None) -> None:
    """Subscribe to ``bus`` and log every event until it closes.

    When ``subscription`` is passed, the caller has already registered it
    synchronously (so any ``publish`` before this coroutine schedules still
    queues). Otherwise we subscribe ourselves.
    """
    log = get_logger("openmimicry.bus")
    sub = subscription if subscription is not None else bus.subscribe()
    async for event in sub:
        level = level_for_event(event)
        payload = {
            "kind": getattr(event, "kind", "?"),
            "ts": getattr(event, "ts", None),
        }
        if isinstance(event, ErrorEvent):
            payload["where"] = event.where
            payload["recoverable"] = event.recoverable
            log.log(level, event.message, **payload)
            continue
        if level >= logging.INFO:
            payload["event"] = event.model_dump(mode="json")
        log.log(level, getattr(event, "kind", "event"), **payload)
