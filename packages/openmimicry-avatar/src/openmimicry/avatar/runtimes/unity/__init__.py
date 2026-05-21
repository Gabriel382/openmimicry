"""Unity bridge avatar runtime (M11).

Backend ←→ Unity sample app: the adapter forwards `AvatarDirective`s
as JSON frames over a pluggable transport (`WSUnityTransport` by
default; `MockUnityTransport` for tests).

See ``docs/modules/post_v0_2_modalities.md`` (M11 section).
"""

from __future__ import annotations

from .adapter import (
    UnityAvatarAdapter,
    UnityTransportUnavailable,
    make_unity_avatar_adapter,
)
from .transports import (
    MockUnityTransport,
    UnityFrame,
    UnityTransport,
    WSUnityTransport,
)

__all__ = [
    "MockUnityTransport",
    "UnityAvatarAdapter",
    "UnityFrame",
    "UnityTransport",
    "UnityTransportUnavailable",
    "WSUnityTransport",
    "make_unity_avatar_adapter",
]
