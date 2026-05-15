"""Hot-reload of the active config file.

Opt-in via ``app.config_watch=true``. When a watched file changes, the
reloader re-runs the loader and publishes ``ConfigUpdated(diff=...)`` on
the bus. Each module decides whether the diff requires action (some keys
hot-reload; others mark "needs restart" — see ``docs/configuration.md`` §4).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from watchfiles import Change, awatch

from ..bus import EventBus
from ..schemas.app import AppConfig
from ..schemas.events import ConfigUpdated
from .loader import diff_dicts, load

__all__ = ["ConfigReloader"]


_log = logging.getLogger(__name__)


LoaderFn = Callable[[], AppConfig]
"""Pluggable loader, useful in tests."""


class ConfigReloader:
    """Watches a file path and publishes ``ConfigUpdated`` events on change.

    The reloader owns a background ``asyncio.Task``. Call :meth:`start` after
    the event loop is running; call :meth:`stop` to cancel it.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        bus: EventBus,
        current: AppConfig,
        loader: LoaderFn | None = None,
        debounce_ms: int = 200,
    ) -> None:
        self._path = Path(path)
        self._bus = bus
        self._current = current
        self._loader: LoaderFn = loader or (lambda: load(self._path))
        self._debounce_ms = debounce_ms
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    # ------------------------------------------------------------------ API

    async def start(self) -> None:
        """Spawn the watch loop. No-op if already running."""
        if self._task is not None and not self._task.done():
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="openmimicry.config.reloader")

    async def stop(self) -> None:
        """Cooperatively stop the watch loop."""
        self._stop_event.set()
        task = self._task
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
        self._task = None

    @property
    def current(self) -> AppConfig:
        return self._current

    # ----------------------------------------------------------- watch loop

    async def _run(self) -> None:
        try:
            async for changes in awatch(
                self._path,
                stop_event=self._stop_event,
                debounce=self._debounce_ms,
                recursive=False,
            ):
                if not self._should_react(changes):
                    continue
                await self._reload_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log.warning("ConfigReloader watch loop crashed: %s", exc, exc_info=True)

    def _should_react(self, changes: set[tuple[Change, str]]) -> bool:
        wanted = str(self._path.resolve())
        for _change_kind, path in changes:
            try:
                if Path(path).resolve() == Path(wanted):
                    return True
            except OSError:  # pragma: no cover
                continue
        return False

    async def _reload_once(self) -> None:
        try:
            new_cfg = self._loader()
        except Exception as exc:
            _log.warning("ConfigReloader: failed to reload %s: %s", self._path, exc)
            return

        before = self._current.model_dump(mode="python")
        after = new_cfg.model_dump(mode="python")
        diff = diff_dicts(before, after)
        if not diff:
            return

        self._current = new_cfg
        self._bus.publish(
            ConfigUpdated(
                ts=_now(),
                diff=diff,
            )
        )


def _now():
    """Wallclock now — wrapped so tests can monkeypatch if needed."""
    return datetime.now(timezone.utc)
