"""External avatar runtime (M12).

A generic WebSocket bridge to third-party renderers. The OpenMimicry
backend speaks the protocol documented in
``docs/external_runtimes.md`` and ``docs/contracts.md`` §9 (External
additive amendment); anyone implementing a compliant renderer can
plug in without touching this package.
"""

from __future__ import annotations

from .adapter import (
    ExternalAvatarAdapter,
    ExternalUnavailable,
    make_external_avatar_adapter,
)
from .client import (
    ExternalClient,
    ExternalClientError,
    ExternalFrame,
    MockExternalClient,
    WSExternalClient,
)

__all__ = [
    "ExternalAvatarAdapter",
    "ExternalClient",
    "ExternalClientError",
    "ExternalFrame",
    "ExternalUnavailable",
    "MockExternalClient",
    "WSExternalClient",
    "make_external_avatar_adapter",
]
