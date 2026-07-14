"""HTTP routes for the M6 FastAPI process.

Every route handler reads the assembled :class:`openmimicry_backend.wiring.Wiring`
off ``request.app.state.wiring``. Routes never import concrete adapter
classes — they use Protocol-typed attributes only.
"""

from __future__ import annotations

from .admin import router as admin_router
from .chat import router as chat_router
from .health import router as health_router
from .mode import router as mode_router
from .pack import router as pack_router

__all__ = [
    "admin_router",
    "chat_router",
    "health_router",
    "mode_router",
    "pack_router",
]
