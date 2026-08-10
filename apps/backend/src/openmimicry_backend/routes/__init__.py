"""HTTP routes for the M6 FastAPI process.

Every route handler reads the assembled :class:`openmimicry_backend.wiring.Wiring`
off ``request.app.state.wiring``. Routes never import concrete adapter
classes — they use Protocol-typed attributes only.
"""

from __future__ import annotations

from .admin import router as admin_router
from .appearance import router as appearance_router
from .chat import router as chat_router
from .companions import router as companions_router
from .dashboard import router as dashboard_router
from .diagnostics import router as diagnostics_router
from .health import router as health_router
from .interaction import router as interaction_router
from .llm import router as llm_router
from .memory import router as memory_router
from .mode import router as mode_router
from .pack import router as pack_router
from .personality import router as personality_router
from .tasks import router as tasks_router
from .tools import router as tools_router
from .voice_clone import router as voice_clone_router
from .voice_profiles import router as voice_profiles_router

__all__ = [
    "admin_router",
    "appearance_router",
    "chat_router",
    "companions_router",
    "dashboard_router",
    "diagnostics_router",
    "health_router",
    "interaction_router",
    "llm_router",
    "memory_router",
    "mode_router",
    "pack_router",
    "personality_router",
    "tasks_router",
    "tools_router",
    "voice_clone_router",
    "voice_profiles_router",
]
