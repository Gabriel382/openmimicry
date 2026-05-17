"""``AvatarOrchestrator`` — owns the runtime, subscribes to the bus, dispatches directives.

Responsibilities:

* Subscribe to the bus on :meth:`start`; for each event, ask the director
  for the next :class:`AvatarDirective`; if non-``None``, ``await
  runtime.apply_directive(d)`` and remember it as the current one.
* Hold-and-return: when a directive carries ``next_state`` +
  ``duration_ms``, schedule a callback that asks the director to
  synthesise the return-to-idle directive and dispatches it. Any newer
  directive cancels the pending timer.
* :meth:`swap_runtime` is the **visual-state-preservation** invariant:
  ``old.shutdown()`` → ``new.load_character(...)`` → re-emit
  ``self._current`` to ``new`` so the avatar's pose persists across the
  swap.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any

from openmimicry.core.bus import EventBus
from openmimicry.core.contracts import AvatarRuntimeAdapter
from openmimicry.core.schemas import AvatarDirective
from openmimicry.core.schemas.app import AvatarConfig

from .director import AvatarDirector

__all__ = ["AvatarOrchestrator"]


_log = logging.getLogger(__name__)


class AvatarOrchestrator:
    """Concrete orchestrator."""

    def __init__(
        self,
        *,
        director: AvatarDirector,
        runtime: AvatarRuntimeAdapter,
        bus: EventBus,
        config: AvatarConfig | None = None,
    ) -> None:
        self._director = director
        self._runtime = runtime
        self._bus = bus
        self._cfg: AvatarConfig = config or AvatarConfig()
        self._current: AvatarDirective | None = None
        self._subscriber_task: asyncio.Task[None] | None = None
        self._return_handle: asyncio.TimerHandle | None = None
        self._started: bool = False
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------- properties

    @property
    def director(self) -> AvatarDirector:
        return self._director

    @property
    def runtime(self) -> AvatarRuntimeAdapter:
        return self._runtime

    @property
    def current(self) -> AvatarDirective | None:
        return self._current

    @property
    def started(self) -> bool:
        return self._started

    # ---------------------------------------------------------------- lifecycle

    async def start(self) -> None:
        if self._started:
            return
        # Load the configured character into the runtime if it exposes the
        # default character config. The pack-loader path lives in
        # ``openmimicry.avatar.pack``; the orchestrator does NOT preload a
        # pack file -- the backend does that during wiring and passes a
        # resolved character_id.
        await self._runtime.load_character(
            self._cfg.pack,
            self._cfg.runtimes.get(self._runtime.name, {}),
        )
        self._started = True
        self._subscriber_task = asyncio.create_task(
            self._consume_bus(), name="openmimicry.avatar.orchestrator"
        )

    async def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        self._cancel_return_timer()
        if self._subscriber_task is not None:
            self._subscriber_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._subscriber_task
            self._subscriber_task = None
        with suppress(Exception):
            await self._runtime.shutdown()

    # --------------------------------------------------------------- dispatch

    async def _consume_bus(self) -> None:
        sub = self._bus.subscribe()
        try:
            async for event in sub:
                await self._handle_event(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            _log.warning("AvatarOrchestrator: bus consumer crashed: %s", exc, exc_info=True)

    async def _handle_event(self, event: Any) -> None:
        try:
            directive = self._director.on_event(event)
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "AvatarDirector raised on %s: %s",
                getattr(event, "kind", "?"),
                exc,
                exc_info=True,
            )
            return
        if directive is None:
            return
        await self._dispatch(directive)

    async def _dispatch(self, directive: AvatarDirective) -> None:
        """Send a directive to the runtime and schedule any return timer."""
        async with self._lock:
            # Any new directive supersedes a pending return-to-idle.
            self._cancel_return_timer()

            try:
                await self._runtime.apply_directive(directive)
            except Exception as exc:  # noqa: BLE001
                _log.warning(
                    "runtime.apply_directive raised: %s", exc, exc_info=True
                )
                return
            self._current = directive

            # Schedule the hold-and-return timer if requested.
            if directive.next_state is not None and directive.duration_ms:
                loop = asyncio.get_running_loop()
                delay_s = max(0.0, directive.duration_ms / 1000.0)
                self._return_handle = loop.call_later(
                    delay_s, self._fire_return, directive.next_state
                )

    def _fire_return(self, next_state: str) -> None:
        """Timer callback: schedule the return-to-idle dispatch on the loop."""
        loop = asyncio.get_running_loop()
        loop.create_task(self._do_return(next_state), name="openmimicry.avatar.return")

    async def _do_return(self, next_state: str) -> None:
        try:
            directive = self._director.apply_return_to(next_state)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            _log.warning("director.apply_return_to raised: %s", exc, exc_info=True)
            return
        await self._dispatch(directive)

    def _cancel_return_timer(self) -> None:
        if self._return_handle is not None:
            self._return_handle.cancel()
            self._return_handle = None

    # ------------------------------------------------------------ swap_runtime

    async def swap_runtime(self, new_runtime: AvatarRuntimeAdapter) -> None:
        """Replace the active runtime, preserving the current visual state.

        Per the brief's DoD: ``old.shutdown()``, ``new.load_character(...)``,
        then ``new.apply_directive(self._current)`` to keep the avatar's
        pose stable across the swap.
        """
        async with self._lock:
            self._cancel_return_timer()
            old = self._runtime
            self._runtime = new_runtime
            with suppress(Exception):
                await old.shutdown()
            await new_runtime.load_character(
                self._cfg.pack,
                self._cfg.runtimes.get(new_runtime.name, {}),
            )
            if self._current is not None:
                with suppress(Exception):
                    await new_runtime.apply_directive(self._current)
