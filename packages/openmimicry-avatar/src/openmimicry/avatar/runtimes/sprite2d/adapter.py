"""``Sprite2DAvatarAdapter`` — the default ``AvatarRuntimeAdapter``.

Translates :class:`AvatarDirective` into the wire message defined in
``docs/contracts.md`` §9 and publishes it via an injected
:class:`WSBridge`. The bridge is provided by M6 (the FastAPI process); in
tests, a small ``FakeBridge`` records every ``publish`` call so assertions
can pin down exact wire output.

Per the brief, the adapter must accept any well-formed ``AvatarDirective``
— including ones with ``gesture`` / ``gaze`` / ``intensity`` fields it
doesn't render — without raising. Unknown ``state`` values fall back to
``pack.default_state`` with a one-shot warning.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from openmimicry.core.schemas import AvatarDirective, CharacterPack

from ...pack import PackLoadError, load_pack
from .projection import build_sprite2d_projection

__all__ = [
    "Sprite2DAvatarAdapter",
    "WSBridge",
    "make_sprite2d_avatar_adapter",
]


_log = logging.getLogger(__name__)


@runtime_checkable
class WSBridge(Protocol):
    """Minimal interface for the WebSocket transport.

    M6 supplies the concrete implementation. Tests pass a ``FakeBridge``
    that records every ``publish`` call into a list.
    """

    async def publish(self, message: dict[str, Any]) -> None: ...


class _NullBridge:
    """Default bridge — drops messages.

    The entry-point factory (``make_sprite2d_avatar_adapter``) uses this so
    the contract conftest can satisfy ``isinstance`` checks without wiring
    a real bridge. Production wiring (M6) always passes a real bridge.
    """

    async def publish(self, message: dict[str, Any]) -> None:
        return None


class Sprite2DAvatarAdapter:
    """Concrete :class:`AvatarRuntimeAdapter` for the 2D frame-sequence path."""

    name: str = "sprite2d"

    def __init__(
        self,
        *,
        pack: CharacterPack | None = None,
        ws_bridge: WSBridge | None = None,
        static_url_prefix: str = "/static/characters",
    ) -> None:
        self.capabilities: set[str] = {"2d", "speaking_variants"}
        self._pack: CharacterPack | None = pack
        self._bridge: WSBridge = ws_bridge or _NullBridge()
        self._url_prefix = static_url_prefix
        self._closed: bool = False
        self._warned_unknown_states: set[str] = set()

    # ----------------------------------------------------------------- API

    async def load_character(self, character_id: str, config: dict[str, Any]) -> None:
        """Swap the active pack and emit a fresh idle directive.

        ``config`` may include a ``pack_path`` override; otherwise the
        adapter loads ``characters/<character_id>`` from CWD as a sane
        default for tests / dev. Production wiring supplies an explicit
        path via ``pack_path`` resolved against ``avatar.pack_roots``.
        """
        pack_path = config.get("pack_path") or f"characters/{character_id}"
        try:
            pack = load_pack(pack_path)
        except PackLoadError as exc:
            _log.warning("Sprite2DAvatarAdapter: failed to load %s: %s", pack_path, exc)
            raise
        if pack.id != character_id:
            _log.warning(
                "Sprite2DAvatarAdapter: pack.id=%r differs from requested %r; using %r",
                pack.id,
                character_id,
                pack.id,
            )
        self._pack = pack
        # Send a fresh idle directive so the frontend has a starting frame.
        idle = AvatarDirective(state=pack.default_state, emotion=pack.default_emotion)
        await self.apply_directive(idle)

    async def apply_directive(self, directive: AvatarDirective) -> None:
        """Build the projection and publish it.

        Never raises on missing pack / unknown state / unsupported field.
        """
        pack = self._pack
        if pack is None:
            _log.warning("Sprite2DAvatarAdapter: apply_directive without a loaded pack; dropping")
            return

        if directive.state not in pack.emotions:
            if directive.state not in self._warned_unknown_states:
                self._warned_unknown_states.add(directive.state)
                _log.warning(
                    "Sprite2DAvatarAdapter: state %r not in pack %r; falling back to %r",
                    directive.state,
                    pack.id,
                    pack.default_state,
                )

        try:
            message = build_sprite2d_projection(
                directive, pack, static_url_prefix=self._url_prefix
            )
        except Exception as exc:  # noqa: BLE001 — never raise
            _log.warning("Sprite2DAvatarAdapter: projection failed: %s", exc, exc_info=True)
            return

        try:
            await self._bridge.publish(message)
        except Exception as exc:  # noqa: BLE001 — transport issues shouldn't poison the bus
            _log.warning("Sprite2DAvatarAdapter: bridge.publish failed: %s", exc, exc_info=True)

    async def set_text(self, text: str) -> None:
        await self._bridge.publish(
            {"type": "bubble.text", "text": text, "complete": True}
        )

    async def start_speaking(self, text: str | None = None) -> None:
        await self._bridge.publish(
            {
                "type": "avatar.directive",
                "runtime": "sprite2d",
                "speaking": True,
                "text": text,
            }
        )

    async def stop_speaking(self) -> None:
        await self._bridge.publish(
            {"type": "avatar.directive", "runtime": "sprite2d", "speaking": False}
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


def make_sprite2d_avatar_adapter(*_args: Any, **_kwargs: Any) -> Sprite2DAvatarAdapter:
    """Entry-point factory used by the contract conftest.

    Returns an adapter with no pack and a null bridge. Real wiring (M6)
    constructs the adapter directly with the resolved pack and a live
    bridge.
    """
    return Sprite2DAvatarAdapter()
