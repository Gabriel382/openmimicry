"""Avatar Protocols — runtime adapter, director, orchestrator.

Source of truth: ``docs/contracts.md`` §5.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..schemas.avatar import AvatarDirective
from ..schemas.events import RuntimeEvent

__all__ = [
    "AvatarDirector",
    "AvatarOrchestrator",
    "AvatarRuntimeAdapter",
]


@runtime_checkable
class AvatarRuntimeAdapter(Protocol):
    """A modality-specific renderer (Sprite2D, Three.js, Live3D, Unity, …).

    Implementations live in ``openmimicry-avatar/runtimes/<modality>/`` and
    advertise their capability set so the orchestrator can refuse incompatible
    directives gracefully (e.g. a gesture directive on a Sprite2D pack).
    """

    name: str
    capabilities: set[str]

    async def load_character(self, character_id: str, config: dict) -> None: ...
    async def apply_directive(self, directive: AvatarDirective) -> None: ...
    async def set_text(self, text: str) -> None: ...
    async def start_speaking(self, text: str | None = None) -> None: ...
    async def stop_speaking(self) -> None: ...
    async def set_visibility(self, visible: bool) -> None: ...
    async def healthcheck(self) -> bool: ...
    async def shutdown(self) -> None: ...


class AvatarDirector(Protocol):
    """Translates ``RuntimeEvent`` into ``AvatarDirective``.

    Stateless from the caller's perspective: side effects (animation timers,
    pack swaps, …) live on the orchestrator.
    """

    def on_event(self, event: RuntimeEvent) -> AvatarDirective | None: ...


class AvatarOrchestrator(Protocol):
    """Owns the chosen ``AvatarRuntimeAdapter`` and its lifecycle.

    ``swap_runtime`` makes hot modality changes (Sprite2D ↔ Three.js) a single
    cooperative operation rather than a process restart.
    """

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def swap_runtime(self, new_runtime: AvatarRuntimeAdapter) -> None: ...
