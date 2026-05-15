"""Contract-test discovery.

Every adapter implementation registers itself under the entry-point group
``openmimicry.contracts.<protocol_name>``. This fixture loads them, builds a
factory list, and parametrises each contract test over it.

When no implementations are registered, the fixture yields nothing — every
contract test still has its ``pytest.skip`` body, so the suite is "wired but
quiet" until M1–M5 land their adapters.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from importlib.metadata import entry_points
from typing import Any

import pytest

__all__ = ["PROTOCOL_GROUPS", "implementations"]


PROTOCOL_GROUPS: tuple[str, ...] = (
    "llm",
    "stt",
    "tts",
    "speech_controller",
    "task_runtime",
    "avatar_runtime",
)


def _load_factories(protocol_name: str) -> list[tuple[str, Callable[[], Any]]]:
    """Load entry points for ``openmimicry.contracts.<protocol_name>``.

    Returns a list of ``(label, factory)`` tuples. Each factory is a no-arg
    callable that builds a fresh instance for the test.
    """
    group = f"openmimicry.contracts.{protocol_name}"
    eps = entry_points()
    # Python 3.10+ — select by group name.
    selected: Iterable[Any]
    try:
        selected = eps.select(group=group)
    except AttributeError:  # pragma: no cover — Py<3.10 (we require 3.11 but be safe).
        selected = [ep for ep in eps if getattr(ep, "group", None) == group]

    out: list[tuple[str, Callable[[], Any]]] = []
    for ep in selected:
        try:
            obj = ep.load()
        except Exception as exc:
            pytest.fail(f"failed to load contract entry point {ep.name!r}: {exc}")
        out.append((ep.name, obj))
    return out


@pytest.fixture
def implementations(request: pytest.FixtureRequest) -> list[tuple[str, Callable[[], Any]]]:
    """Per-test fixture: pass the protocol short-name via ``request.param``.

    Example::

        @pytest.mark.parametrize("implementations", ["llm"], indirect=True)
        def test_healthcheck(implementations): ...
    """
    protocol_name = getattr(request, "param", None)
    if protocol_name is None:
        pytest.fail(
            "the `implementations` fixture requires indirect parametrisation "
            "with the protocol short-name (e.g. 'llm')."
        )
    return _load_factories(protocol_name)
