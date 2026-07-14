"""Process-level lifecycle helpers — signal handlers, graceful shutdown.

These helpers are intentionally small. The backend (M6) wires them; tests
build their own ``Runtime`` and drive it directly.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Iterable

from .runtime import Runtime

__all__ = ["DEFAULT_STOP_SIGNALS", "install_signal_handlers"]


_log = logging.getLogger(__name__)


DEFAULT_STOP_SIGNALS: tuple[signal.Signals, ...] = (signal.SIGINT, signal.SIGTERM)
"""Signals that should trigger a graceful shutdown."""


def install_signal_handlers(
    runtime: Runtime,
    *,
    signals: Iterable[signal.Signals] | None = None,
    loop: asyncio.AbstractEventLoop | None = None,
) -> None:
    """Install handlers that call ``runtime.stop()`` on SIGINT/SIGTERM.

    On Windows where ``add_signal_handler`` isn't available, this falls back
    to ``signal.signal`` with a thread-safe ``call_soon_threadsafe`` shim.
    """
    target_signals = tuple(signals) if signals is not None else DEFAULT_STOP_SIGNALS
    target_loop = loop or asyncio.get_event_loop()

    def _shutdown() -> None:
        _log.info("signal received; stopping runtime")
        target_loop.create_task(runtime.stop())

    for sig in target_signals:
        try:
            target_loop.add_signal_handler(sig, _shutdown)
        except (NotImplementedError, RuntimeError):
            # Windows: fall back to signal.signal.
            def _legacy_handler(_signum: int, _frame: object, _sig: signal.Signals = sig) -> None:
                target_loop.call_soon_threadsafe(_shutdown)

            signal.signal(sig, _legacy_handler)
