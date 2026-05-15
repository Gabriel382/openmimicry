"""Mock voice adapters — stub placeholders.

Phase 0 contract freeze ships the import-stable names so that consumers can
write ``from openmimicry.voice.mocks import MockSTTAdapter`` today and get a
loud, debuggable error if they instantiate it. The real, programmable mocks
are delivered by **M2**; see ``docs/modules/M2_voice.md`` and
``docs/contracts.md`` §8.

DO NOT add real behaviour here. M2 replaces this file wholesale.
"""

from __future__ import annotations

from typing import Any

__all__ = ["MockSTTAdapter", "MockTTSAdapter"]


class MockSTTAdapter:
    """Placeholder for the M2 programmable STT mock."""

    name: str = "mock"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError(
            "MockSTTAdapter is not implemented yet. "
            "It will be delivered by M2 — see docs/modules/M2_voice.md."
        )


class MockTTSAdapter:
    """Placeholder for the M2 recording TTS mock."""

    name: str = "mock"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError(
            "MockTTSAdapter is not implemented yet. "
            "It will be delivered by M2 — see docs/modules/M2_voice.md."
        )
