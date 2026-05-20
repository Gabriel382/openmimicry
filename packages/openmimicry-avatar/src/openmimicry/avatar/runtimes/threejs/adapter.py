"""``ThreeJSAvatarAdapter`` — the second concrete ``AvatarRuntimeAdapter``.

Same shape as :class:`Sprite2DAvatarAdapter`: receives
:class:`AvatarDirective`s, builds a wire message via
:func:`build_threejs_projection`, and publishes it through an injected
:class:`WSBridge`. The adapter is the **only** place that touches the
filesystem (via :func:`load_pack`) — the projector is pure.

Per the brief: never raise on unsupported fields. Unknown ``gesture``s
are dropped silently; non-Three-friendly ``pack.kind`` is logged once
and the pack still loads (the frontend may show an error placeholder).
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from openmimicry.core.schemas import AvatarDirective, CharacterPack

from ...pack import PackLoadError, load_pack
from .projection import build_threejs_projection

__all__ = [
    "ThreeJSAvatarAdapter",
    "ThreeJSPackError",
    "WSBridge",
    "make_threejs_avatar_adapter",
]


_log = logging.getLogger(__name__)


class ThreeJSPackError(ValueError):
    """Raised when a pack obviously isn't compatible with the Three.js runtime."""


@runtime_checkable
class WSBridge(Protocol):
    """Minimal interface for the WebSocket transport.

    M6 supplies the concrete implementation. Tests pass a ``FakeBridge``
    that records every ``publish`` call into a list.
    """

    async def publish(self, message: dict[str, Any]) -> None: ...


class _NullBridge:
    """Default bridge — drops messages. Used by the entry-point factory."""

    async def publish(self, message: dict[str, Any]) -> None:
        return None


_THREEJS_FRIENDLY_KINDS: frozenset[str] = frozenset({"vrm", "gltf", "threejs"})


class ThreeJSAvatarAdapter:
    """Concrete :class:`AvatarRuntimeAdapter` for the Three.js modality."""

    name: str = "threejs"

    def __init__(
        self,
        *,
        pack: CharacterPack | None = None,
        ws_bridge: WSBridge | None = None,
        static_url_prefix: str = "/static/characters",
        runtime_cfg: dict[str, Any] | None = None,
    ) -> None:
        self.capabilities: set[str] = {"3d", "gestures", "gaze", "expressions"}
        self._pack: CharacterPack | None = pack
        self._bridge: WSBridge = ws_bridge or _NullBridge()
        self._url_prefix = static_url_prefix
        self._runtime_cfg: dict[str, Any] = dict(runtime_cfg or {})
        self._closed: bool = False
        self._warned_unknown_kind: bool = False

    # ----------------------------------------------------------------- API

    async def load_character(self, character_id: str, config: dict[str, Any]) -> None:
        """Load the requested pack and emit a fresh idle directive."""
        cfg = dict(config or {})
        pack_path = cfg.get("pack_path") or f"characters/{character_id}"
        try:
            pack = load_pack(pack_path)
        except PackLoadError as exc:
            _log.warning("ThreeJSAvatarAdapter: failed to load %s: %s", pack_path, exc)
            raise

        if pack.id != character_id:
            _log.warning(
                "ThreeJSAvatarAdapter: pack.id=%r differs from requested %r; using %r",
                pack.id,
                character_id,
                pack.id,
            )

        if pack.kind not in _THREEJS_FRIENDLY_KINDS:
            if not self._warned_unknown_kind:
                self._warned_unknown_kind = True
                _log.warning(
                    "ThreeJSAvatarAdapter: pack.kind=%r is not vrm/gltf; "
                    "frontend may fail to load %r",
                    pack.kind,
                    pack.id,
                )

        self._pack = pack
        # Merge any runtime overrides from the pack config so the
        # projection picks them up.
        if isinstance(cfg.get("runtime"), dict):
            self._runtime_cfg.update(cfg["runtime"])

        idle = AvatarDirective(state=pack.default_state, emotion=pack.default_emotion)
        await self.apply_directive(idle)

    async def apply_directive(self, directive: AvatarDirective) -> None:
        """Build the projection and publish it. Never raises."""
        pack = self._pack
        if pack is None:
            _log.warning(
                "ThreeJSAvatarAdapter: apply_directive without a loaded pack; dropping"
            )
            return

        try:
            message = build_threejs_projection(
                directive,
                pack,
                static_url_prefix=self._url_prefix,
                runtime_cfg=self._runtime_cfg,
            )
        except Exception as exc:  # noqa: BLE001 — never raise
            _log.warning(
                "ThreeJSAvatarAdapter: projection failed: %s", exc, exc_info=True
            )
            return

        try:
            await self._bridge.publish(message)
        except Exception as exc:  # noqa: BLE001 — transport issues shouldn't poison the bus
            _log.warning(
                "ThreeJSAvatarAdapter: bridge.publish failed: %s", exc, exc_info=True
            )

    async def set_text(self, text: str) -> None:
        await self._bridge.publish(
            {"type": "bubble.text", "text": text, "complete": True}
        )

    async def start_speaking(self, text: str | None = None) -> None:
        await self._bridge.publish(
            {
                "type": "avatar.directive",
                "runtime": "threejs",
                "speaking": True,
                "text": text,
            }
        )

    async def stop_speaking(self) -> None:
        await self._bridge.publish(
            {"type": "avatar.directive", "runtime": "threejs", "speaking": False}
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
        # Idempotent — second call is a no-op.
        self._closed = True


def make_threejs_avatar_adapter(*_args: Any, **_kwargs: Any) -> ThreeJSAvatarAdapter:
    """Entry-point factory used by the contract conftest.

    Returns an adapter with no pack and a null bridge — sufficient for
    Protocol-isinstance assertions. Real wiring (M6) constructs the
    adapter directly with the resolved pack and a live bridge.
    """
    return ThreeJSAvatarAdapter()
