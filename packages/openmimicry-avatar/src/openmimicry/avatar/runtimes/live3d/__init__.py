"""Live3D avatar runtime — the M10 modality.

Live3D builds on M9 by composition: same scene, same loaders, plus
client-side drivers for mouth (audio amplitude or viseme hints),
procedural idle motion, and gaze tracking. The Python adapter publishes
the M9 projection plus a ``live`` block that the frontend reads to
enable each driver.

See ``docs/modules/post_v0_2_modalities.md`` (M10 section).
"""

from __future__ import annotations

from .adapter import (
    Live3DAvatarAdapter,
    WSBridge,
    make_live3d_avatar_adapter,
)
from .projection import build_live3d_projection

__all__ = [
    "Live3DAvatarAdapter",
    "WSBridge",
    "build_live3d_projection",
    "make_live3d_avatar_adapter",
]
