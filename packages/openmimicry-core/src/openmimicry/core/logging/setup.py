"""structlog configuration for OpenMimicry.

Two renderers:

* ``json`` — newline-delimited JSON. The default for headless / agent use.
* ``text`` — a console renderer with colour when a TTY is present. For dev.

Every record is enriched with ``app_version`` and ``pid`` so JSON logs are
correlatable across processes (CI, local dev, packaged release).
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Literal

import structlog

__all__ = ["LogFormat", "configure_logging", "get_logger"]


LogFormat = Literal["json", "text"]


_CONFIGURED: bool = False


def _try_import_version() -> str:
    try:
        from .. import __version__  # type: ignore[attr-defined]

        return str(__version__)
    except Exception:
        return "0.0.0"


def _add_app_context(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    event_dict.setdefault("app_version", _try_import_version())
    event_dict.setdefault("pid", os.getpid())
    return event_dict


def configure_logging(
    *,
    level: str = "INFO",
    format: LogFormat = "json",
    stream: Any | None = None,
    force: bool = False,
) -> None:
    """Configure structlog + the stdlib root logger.

    Safe to call multiple times; subsequent calls return without re-wiring
    unless ``force=True``. Pass ``stream`` to redirect output in tests.
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    numeric = logging.getLevelName(level.upper())
    if not isinstance(numeric, int):
        raise ValueError(f"invalid log level: {level!r}")

    out = stream if stream is not None else sys.stderr

    handler = logging.StreamHandler(out)
    handler.setLevel(numeric)
    root = logging.getLogger()
    # Replace handlers so repeated calls don't multiply output.
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(numeric)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_app_context,
    ]

    if format == "json":
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=out.isatty() if hasattr(out, "isatty") else False
        )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric),
        logger_factory=structlog.PrintLoggerFactory(file=out),
        cache_logger_on_first_use=True,
    )
    _CONFIGURED = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger. Configures lazily with defaults if needed."""
    if not _CONFIGURED:
        configure_logging()
    return structlog.get_logger(name)  # type: ignore[no-any-return]
