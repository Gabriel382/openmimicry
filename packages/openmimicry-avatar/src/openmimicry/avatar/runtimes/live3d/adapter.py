"""``Live3DAvatarAdapter`` — composition over the M9 adapter.

Reuses the Three.js pack-load + bridge-publish pipeline. The only
difference is the projection: it sets ``runtime = "live3d"`` and
appends the ``live`` block.

Per the M10 brief: "Build on M9 by composition — do not modify the
Three.js runtime." The adapter inherits *behaviour* but composes
explicitly so any future divergence is local.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from openmimicry.core.schemas import AvatarDirective, CharacterPack

from ...pack import PackLoadError, load_pack
from .projection import build_live3d_projection

__all__ = [
    "Live3DAvatarAdapter",
    "WSBridge",
    "make_live3d_avatar_adapter",
]


_log = logging.getLogger(__name__)


@runtime_checkable
class WSBridge(Protocol):
    """Minimal interface for the WebSocket transport."""

    async def publish(self, message: dict[str, Any]) -> None: ...


class _NullBridge:
    async def publish(self, message: dict[str, Any]) -> None:
        return None


# Packs that the renderer is happy with. Same rule as M9 — we warn-and-
# load anything else rather than raising.
_LIVE3D_FRIENDLY_KINDS: frozenset[str] = frozenset({"vrm", "gltf", "threejs"})


class Live3DAvatarAdapter:
    """Concrete :class:`AvatarRuntimeAdapter` for the Live3D modality."""

    name: str = "live3d"

    def __init__(
        self,
        *,
        pack: CharacterPack | None = None,
        ws_bridge: WSBridge | None = None,
        static_url_prefix: str = "/static/characters",
        runtime_cfg: dict[str, Any] | None = None,
    ) -> None:
        self.capabilities: set[str] = {
            "3d",
            "gestures",
            "gaze",
            "expressions",
            "mouth",
            "procedural_idle",
        }
        self._pack: CharacterPack | None = pack
        self._bridge: WSBridge = ws_bridge or _NullBridge()
        self._url_prefix = static_url_prefix
        self._runtime_cfg: dict[str, Any] = dict(runtime_cfg or {})
        self._closed: bool = False
        self._warned_unknown_kind: bool = False

    # ----------------------------------------------------------------- API

    async def load_character(self, character_id: str, config: dict[str, Any]) -> None:
        cfg = dict(config or {})
        pack_path = cfg.get("pack_path") or f"characters/{character_id}"
        try:
            pack = load_pack(pack_path)
        except PackLoadError as exc:
            _log.warning("Live3DAvatarAdapter: failed to load %s: %s", pack_path, exc)
            raise

        if pack.id != character_id:
            _log.warning(
                "Live3DAvatarAdapter: pack.id=%r differs from requested %r; using %r",
                pack.id,
                character_id,
                pack.id,
            )

        if pack.kind not in _LIVE3D_FRIENDLY_KINDS and not self._warned_unknown_kind:
            self._warned_unknown_kind = True
            _log.warning(
                "Live3DAvatarAdapter: pack.kind=%r is not vrm/gltf; "
                "frontend may fail to load %r",
                pack.kind,
                pack.id,
            )

        self._pack = pack
        if isinstance(cfg.get("runtime"), dict):
            self._runtime_cfg.update(cfg["runtime"])

        idle = AvatarDirective(state=pack.default_state, emotion=pack.default_emotion)
        await self.apply_directive(idle)

    async def apply_directive(self, directive: AvatarDirective) -> None:
        pack = self._pack
        if pack is None:
            _log.warning(
                "Live3DAvatarAdapter: apply_directive without a loaded pack; dropping"
            )
            return

        try:
            message = build_live3d_projection(
                directive,
                pack,
                static_url_prefix=self._url_prefix,
                runtime_cfg=self._runtime_cfg,
            )
        except Exception as exc:  # noqa: BLE001 — never raise
            _log.warning(
                "Live3DAvatarAdapter: projection failed: %s", exc, exc_info=True
            )
            return

        try:
            await self._bridge.publish(message)
        except Exception as exc:  # noqa: BLE001 — transport issues shouldn't poison the bus
            _log.warning(
                "Live3DAvatarAdapter: bridge.publish failed: %s", exc, exc_info=True
            )

    async def set_text(self, text: str) -> None:
        await self._bridge.publish(
            {"type": "bubble.text", "text": text, "complete": True}
        )

    async def start_speaking(self, text: str | None = None) -> None:
        await self._bridge.publish(
            {
                "type": "avatar.directive",
                "runtime": "live3d",
                "speaking": True,
                "text": text,
            }
        )

    async def stop_speaking(self) -> None:
        await self._bridge.publish(
            {"type": "avatar.directive", "runtime": "live3d", "speaking": False}
        )

    async def set_visibility(self, visible: bool) -> None:
        await self._bridge.publish(
            {
                "type": "system.notice",
                "kind": "visibility",
                "level": "info",
                "message": "visibility",
                "visible": visible,
            }
        )

    async def healthcheck(self) -> bool:
        return not self._closed

    async def shutdown(self) -> None:
        self._closed = True


def make_live3d_avatar_adapter(*_args: Any, **_kwargs: Any) -> Live3DAvatarAdapter:
    """Entry-point factory used by the contract conftest."""
    return Live3DAvatarAdapter()
