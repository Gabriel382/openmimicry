"""Sprite2D avatar runtime — the default modality.

Reads :class:`AvatarDirective`s and publishes ``avatar.directive`` messages
shaped per the wire protocol in ``docs/contracts.md`` §9. The frontend
:mod:`apps.desktop.frontend.src.runtimes.sprite2d` consumes those messages
and renders the right frame folder at the right fps.
"""

from __future__ import annotations

from .adapter import Sprite2DAvatarAdapter, WSBridge, make_sprite2d_avatar_adapter
from .projection import build_sprite2d_projection

__all__ = [
    "Sprite2DAvatarAdapter",
    "WSBridge",
    "build_sprite2d_projection",
    "make_sprite2d_avatar_adapter",
]
