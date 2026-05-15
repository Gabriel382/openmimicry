"""Mock avatar runtime — stub placeholder.

Phase 0 contract freeze ships the import-stable name so that consumers can
write ``from openmimicry.avatar.mocks import MockAvatarRuntimeAdapter`` today
and get a loud, debuggable error if they instantiate it. The real recording
mock is delivered by **M3**; see ``docs/modules/M3_avatar_core.md`` and
``docs/contracts.md`` §8.

DO NOT add real behaviour here. M3 replaces this file wholesale.
"""

from __future__ import annotations

from typing import Any, ClassVar

__all__ = ["MockAvatarRuntimeAdapter"]


class MockAvatarRuntimeAdapter:
    """Placeholder for the M3 recording avatar mock.

    The real signature exposes ``directives_received: list[AvatarDirective]``.
    """

    name: str = "mock"
    capabilities: ClassVar[set[str]] = {"2d"}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError(
            "MockAvatarRuntimeAdapter is not implemented yet. "
            "It will be delivered by M3 — see docs/modules/M3_avatar_core.md."
        )
