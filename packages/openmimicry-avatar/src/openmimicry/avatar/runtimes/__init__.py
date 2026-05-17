"""Avatar runtimes — Sprite2D / Three.js / Unity / etc.

M3 ships only the Protocol re-export and the mock. Concrete runtimes are
delivered by M4 (Sprite2D), M9 (Three.js), and the post-v0.2 modalities.
"""

from __future__ import annotations

from .base import AvatarRuntimeAdapter

__all__ = ["AvatarRuntimeAdapter"]
