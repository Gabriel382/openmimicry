"""Concrete ``EventBus`` — in-process pub/sub with bounded per-subscriber queues.

The shape of this class is frozen by ``openmimicry.core.contracts.bus``. This
module is the M0-shipped implementation. The single instance is owned by
``Runtime``; modules receive it as a dependency rather than reaching for a
process-global singleton.

Drop policy
-----------

Each subscriber owns its own ``asyncio.Queue`` of ``maxsize`` (default 1024).
``publish`` is non-blocking; if a subscriber's queue is full the **oldest**
event is dropped to make room for the newest, and a single warning per
subscriber is logged. This favours liveness of the producer (typically the
adapter thread) over delivery guarantees on a stalled consumer.

If you need lossless delivery, drain ``subscribe()`` faster than the producer.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from .schemas.events import RuntimeEvent

__all__ = ["DEFAULT_QUEUE_MAXSIZE", "EventBus"]


DEFAULT_QUEUE_MAXSIZE: int = 1024


_log = logging.getLogger(__name__)


class _Subscription:
    """One live subscription. Owns its queue and a one-shot warn flag."""

    __slots__ = ("_closed", "_warned", "queue")

    def __init__(self, maxsize: int) -> None:
        self.queue: asyncio.Queue[RuntimeEvent | None] = asyncio.Queue(maxsize=maxsize)
        self._warned: bool = False
        self._closed: bool = False

    @property
    def closed(self) -> bool:
        return self._closed

    def offer(self, event: RuntimeEvent) -> None:
        """Non-blocking put. Drops the oldest event if the queue is full."""
        if self._closed:
            return
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                self.queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                self.queue.put_nowait(event)
            if not self._warned:
                self._warned = True
                _log.warning(
                    "EventBus subscriber fell behind; dropping oldest events "
                    "(maxsize=%d). Drain subscribe() faster or raise maxsize.",
                    self.queue.maxsize,
                )

    def close(self) -> None:
        """Send a sentinel so a pending ``await get()`` wakes up and stops."""
        if self._closed:
            return
        self._closed = True
        try:
            self.queue.put_nowait(None)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                self.queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                self.queue.put_nowait(None)


class EventBus:
    """The concrete in-process event bus."""

    def __init__(self, *, maxsize: int = DEFAULT_QUEUE_MAXSIZE) -> None:
        self._maxsize = maxsize
        self._subs: list[_Subscription] = []
        self._closed: bool = False

    def publish(self, event: RuntimeEvent) -> None:
        """Fan out one event to every active subscriber. Non-blocking."""
        if self._closed:
            return
        self._reap_closed()
        for sub in self._subs:
            sub.offer(event)

    def subscribe(self) -> AsyncIterator[RuntimeEvent]:
        """Open a new subscription. Closes when the bus closes.

        Registration is synchronous at call time so any ``publish`` happening
        before the caller starts iterating still queues for this subscriber.
        The returned async iterator drains that queue until the sentinel.
        """
        self._reap_closed()
        sub = _Subscription(maxsize=self._maxsize)
        if self._closed:
            sub.close()
        else:
            self._subs.append(sub)
        return self._iter(sub)

    async def _iter(self, sub: _Subscription) -> AsyncIterator[RuntimeEvent]:
        """Drain ``sub`` until the bus or the subscriber closes."""
        try:
            while True:
                item = await sub.queue.get()
                if item is None:
                    return
                yield item
        finally:
            sub.close()
            with contextlib.suppress(ValueError):
                self._subs.remove(sub)

    async def aclose(self) -> None:
        """Drain and close every subscriber. Safe to call multiple times."""
        if self._closed:
            return
        self._closed = True
        for sub in list(self._subs):
            sub.close()
        # Drop all references so subscriber_count reflects closed state even
        # for subscribers whose async-generator finally hasn't run yet.
        self._subs.clear()
        await asyncio.sleep(0)

    def _reap_closed(self) -> None:
        """Drop any subscriptions whose underlying queue has been closed."""
        self._subs[:] = [s for s in self._subs if not s.closed]

    @property
    def subscriber_count(self) -> int:
        """The number of currently-open subscribers. Mostly useful in tests."""
        self._reap_closed()
        return len(self._subs)

    @property
    def closed(self) -> bool:
        return self._closed
