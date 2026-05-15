"""Mock task runtime — stub placeholder.

Phase 0 contract freeze ships the import-stable name so that consumers can
write ``from openmimicry.tasks.mocks import MockTaskRuntimeAdapter`` today
and get a loud, debuggable error if they instantiate it. The real, scripted
mock is delivered by **M5**; see ``docs/modules/M5_tasks.md`` and
``docs/contracts.md`` §8.

DO NOT add real behaviour here. M5 replaces this file wholesale.
"""

from __future__ import annotations

from typing import Any, ClassVar

__all__ = ["MockTaskRuntimeAdapter"]


class MockTaskRuntimeAdapter:
    """Placeholder for the M5 scripted task runtime mock."""

    name: str = "mock"
    capabilities: ClassVar[set[str]] = {"text"}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError(
            "MockTaskRuntimeAdapter is not implemented yet. "
            "It will be delivered by M5 — see docs/modules/M5_tasks.md."
        )
