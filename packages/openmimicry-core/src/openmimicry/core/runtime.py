"""``Runtime`` — wire EventBus + AppConfig + RuntimeStore + logging together.

The Runtime is the single object every other module receives at startup. It
owns the bus, the live config snapshot, the live store, and the background
tasks that keep the store in sync and the logs flowing.

Use it as an ``async with`` context manager::

    async with Runtime(config=AppConfig()) as rt:
        rt.bus.publish(some_event)
        # rt.store reflects the merged state
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from .bus import EventBus
from .config.reloader import ConfigReloader
from .logging.bus_tap import bus_tap_loop
from .logging.setup import configure_logging
from .schemas.app import AppConfig
from .store import RuntimeStore

__all__ = ["Runtime", "create_runtime"]


_log = logging.getLogger(__name__)


class Runtime:
    """The runtime container shared by every module.

    Attributes are read-only after ``start()`` for everything but :attr:`store`
    (which is a moving target updated by the internal store-updater task).
    """

    def __init__(
        self,
        *,
        config: AppConfig,
        bus: EventBus | None = None,
        config_path: str | None = None,
    ) -> None:
        self._config = config
        self._bus = bus or EventBus()
        self._store = RuntimeStore()
        self._config_path = config_path

        self._tasks: list[asyncio.Task[None]] = []
        self._reloader: ConfigReloader | None = None
        self._started: bool = False
        self._stopping: bool = False

    # ------------------------------------------------------------- properties

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def bus(self) -> EventBus:
        return self._bus

    @property
    def store(self) -> RuntimeStore:
        return self._store

    @property
    def reloader(self) -> ConfigReloader | None:
        return self._reloader

    @property
    def started(self) -> bool:
        return self._started

    # ---------------------------------------------------------------- lifecycle

    async def start(self) -> None:
        """Wire up logging, subscribe the bus tap, optionally start the reloader.

        Subscriptions for both the store-updater and the bus-tap are opened
        synchronously here, *before* the background tasks are scheduled, so
        any ``publish`` issued immediately after ``start()`` returns is
        guaranteed to land in both queues.
        """
        if self._started:
            return
        # 1. logging
        configure_logging(level=self._config.app.log_level, format=self._config.app.log_format)

        # 2. store updater — subscribe synchronously, then iterate in a task.
        store_sub = self._bus.subscribe()
        self._tasks.append(
            asyncio.create_task(
                self._store_updater(store_sub),
                name="openmimicry.runtime.store_updater",
            )
        )

        # 3. bus tap (structured log of every event) — same pattern.
        tap_sub = self._bus.subscribe()
        self._tasks.append(
            asyncio.create_task(
                bus_tap_loop(self._bus, subscription=tap_sub),
                name="openmimicry.runtime.bus_tap",
            )
        )

        # 4. config reloader (opt-in)
        if self._config.app.config_watch and self._config_path:
            self._reloader = ConfigReloader(
                self._config_path,
                bus=self._bus,
                current=self._config,
            )
            await self._reloader.start()

        self._started = True

    async def stop(self) -> None:
        """Cancel background tasks and close the bus. Idempotent."""
        if self._stopping or not self._started:
            return
        self._stopping = True

        if self._reloader is not None:
            await self._reloader.stop()
            self._reloader = None

        await self._bus.aclose()

        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with suppress(asyncio.CancelledError, Exception):
                await task
        self._tasks.clear()

        self._started = False
        self._stopping = False

    async def __aenter__(self) -> Runtime:
        await self.start()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.stop()

    # --------------------------------------------------------------- internals

    async def _store_updater(self, subscription) -> None:
        async for event in subscription:
            try:
                self._store = self._store.update(event)
            except Exception as exc:
                _log.warning(
                    "RuntimeStore.update raised on %s: %s",
                    getattr(event, "kind", "?"),
                    exc,
                    exc_info=True,
                )


@asynccontextmanager
async def create_runtime(
    config: AppConfig,
    *,
    bus: EventBus | None = None,
    config_path: str | None = None,
) -> AsyncIterator[Runtime]:
    """Convenience async-context factory.

    Example::

        async with create_runtime(cfg) as rt:
            ...
    """
    rt = Runtime(config=config, bus=bus, config_path=config_path)
    try:
        await rt.start()
        yield rt
    finally:
        await rt.stop()
