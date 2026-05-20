"""Three.js avatar runtime — the M9 modality.

Consumes :class:`AvatarDirective`s and publishes ``avatar.directive``
messages shaped for the Three.js / VRM renderer in
``apps/desktop/frontend/src/runtimes/threejs``.

The wire-message extension is documented in ``docs/contracts.md`` §9
under the *Three.js projection* additive amendment.
"""

from __future__ import annotations

from .adapter import (
    ThreeJSAvatarAdapter,
    ThreeJSPackError,
    WSBridge,
    make_threejs_avatar_adapter,
)
from .projection import build_threejs_projection

__all__ = [
    "ThreeJSAvatarAdapter",
    "ThreeJSPackError",
    "WSBridge",
    "build_threejs_projection",
    "make_threejs_avatar_adapter",
]
