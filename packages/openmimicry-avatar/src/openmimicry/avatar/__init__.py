"""openmimicry-avatar: pack loader, director, orchestrator, mock runtime.

Exports
-------

* :class:`AvatarRuntimeAdapter` — re-exported Protocol.
* :class:`MockAvatarRuntimeAdapter` — recording mock fixture.
* :class:`AvatarDirector` — state machine (RuntimeEvent -> AvatarDirective).
* :class:`AvatarOrchestrator` — owns the active runtime; supports
  ``swap_runtime`` with visual-state preservation.
* :func:`load_pack`, :func:`validate_pack`, :class:`ValidationReport`,
  :class:`PackLoadError` — character-pack loader / validator.

M3 ships only the substrate. Concrete runtimes (Sprite2D, Three.js,
Live3D, Unity, External) plug in via the
``openmimicry.contracts.avatar_runtime`` entry point.
"""

from __future__ import annotations

from openmimicry.core.contracts import AvatarRuntimeAdapter

from .director import AvatarDirector
from .mocks import MockAvatarRuntimeAdapter
from .orchestrator import AvatarOrchestrator
from .pack import PackLoadError, ValidationReport, load_pack, validate_pack
from .runtimes.sprite2d import (
    Sprite2DAvatarAdapter,
    WSBridge,
    build_sprite2d_projection,
)

__all__ = [
    "AvatarDirector",
    "AvatarOrchestrator",
    "AvatarRuntimeAdapter",
    "MockAvatarRuntimeAdapter",
    "PackLoadError",
    "Sprite2DAvatarAdapter",
    "ValidationReport",
    "WSBridge",
    "build_sprite2d_projection",
    "load_pack",
    "validate_pack",
]

__version__ = "0.2.0a0"
