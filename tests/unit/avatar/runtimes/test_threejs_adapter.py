"""Unit tests for ``ThreeJSAvatarAdapter``.

Mirrors the structure of ``test_sprite2d_adapter.py``: a tiny
``FakeBridge`` records every ``publish(...)`` call so we can assert the
exact wire payload. The adapter is constructed with a fake pack that we
build via Pydantic — no disk IO.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from openmimicry.avatar.runtimes.threejs.adapter import (
    ThreeJSAvatarAdapter,
    WSBridge,
)
from openmimicry.core.contracts import AvatarRuntimeAdapter
from openmimicry.core.schemas import AvatarDirective, CharacterPack, EmotionFrames

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "packs"


class FakeBridge:
    name = "fake-bridge"

    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []

    async def publish(self, message: dict[str, Any]) -> None:
        self.published.append(message)


def _pack(**overrides) -> CharacterPack:
    base = dict(
        schema_version=1,
        id="octomimic_vrm",
        name="OctomimicVRM",
        kind="vrm",
        default_state="idle",
        default_emotion="neutral",
        emotions={"idle": EmotionFrames(frames=["a.png"])},
    )
    base.update(overrides)
    return CharacterPack(**base)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


def test_adapter_satisfies_avatar_runtime_protocol() -> None:
    assert isinstance(ThreeJSAvatarAdapter(), AvatarRuntimeAdapter)


def test_runtime_name_and_capabilities() -> None:
    adapter = ThreeJSAvatarAdapter()
    assert adapter.name == "threejs"
    assert {"3d", "gestures", "gaze", "expressions"} <= adapter.capabilities


# ---------------------------------------------------------------------------
# Lifecycle + dispatch
# ---------------------------------------------------------------------------


async def test_apply_directive_publishes_projection() -> None:
    bridge = FakeBridge()
    adapter = ThreeJSAvatarAdapter(pack=_pack(), ws_bridge=bridge)
    await adapter.apply_directive(
        AvatarDirective(state="speaking", emotion="happy", speaking=True, intensity=0.5)
    )
    assert len(bridge.published) == 1
    msg = bridge.published[0]
    assert msg["runtime"] == "threejs"
    assert msg["expression"] == "happy"
    assert msg["intensity"] == 0.5


async def test_apply_directive_without_pack_drops_quietly() -> None:
    bridge = FakeBridge()
    adapter = ThreeJSAvatarAdapter(ws_bridge=bridge)
    await adapter.apply_directive(AvatarDirective(state="idle"))
    assert bridge.published == []


async def test_apply_directive_never_raises_on_unknown_field_combinations() -> None:
    bridge = FakeBridge()
    adapter = ThreeJSAvatarAdapter(pack=_pack(), ws_bridge=bridge)
    # `gesture` is unknown to the projector; this must not raise.
    await adapter.apply_directive(
        AvatarDirective(state="idle", emotion="happy", gesture="definitely-not-known")
    )
    assert len(bridge.published) == 1
    assert "gestureClip" not in bridge.published[0]


async def test_start_stop_speaking_emit_quick_toggles() -> None:
    bridge = FakeBridge()
    adapter = ThreeJSAvatarAdapter(pack=_pack(), ws_bridge=bridge)
    await adapter.start_speaking("hi")
    await adapter.stop_speaking()
    assert bridge.published[0]["speaking"] is True
    assert bridge.published[0]["text"] == "hi"
    assert bridge.published[1]["speaking"] is False


async def test_set_text_emits_bubble_message() -> None:
    bridge = FakeBridge()
    adapter = ThreeJSAvatarAdapter(pack=_pack(), ws_bridge=bridge)
    await adapter.set_text("hello")
    assert bridge.published[0] == {"type": "bubble.text", "text": "hello", "complete": True}


async def test_set_visibility_emits_system_notice() -> None:
    bridge = FakeBridge()
    adapter = ThreeJSAvatarAdapter(pack=_pack(), ws_bridge=bridge)
    await adapter.set_visibility(False)
    msg = bridge.published[-1]
    assert msg["type"] == "system.notice"
    assert msg["visible"] is False


async def test_healthcheck_and_shutdown() -> None:
    adapter = ThreeJSAvatarAdapter()
    assert await adapter.healthcheck() is True
    await adapter.shutdown()
    assert await adapter.healthcheck() is False
    # Double shutdown must be a no-op (idempotent).
    await adapter.shutdown()


async def test_bridge_errors_dont_propagate() -> None:
    class BoomBridge:
        async def publish(self, message):  # noqa: D401, ANN001
            raise RuntimeError("network down")

    adapter = ThreeJSAvatarAdapter(pack=_pack(), ws_bridge=BoomBridge())
    # Must not raise.
    await adapter.apply_directive(AvatarDirective(state="idle"))


# ---------------------------------------------------------------------------
# Pack-load path (uses fixture pack on disk)
# ---------------------------------------------------------------------------


async def test_load_character_warns_on_non_threejs_kind_but_loads() -> None:
    # `good_pack` is kind=sprite2d (from the M3 fixture). The Three.js
    # adapter logs a warning and continues — and the projection still
    # publishes because the projector is permissive.
    bridge = FakeBridge()
    adapter = ThreeJSAvatarAdapter(ws_bridge=bridge)
    await adapter.load_character("good_pack", {"pack_path": str(FIXTURES / "good_pack")})
    assert len(bridge.published) == 1
    assert bridge.published[0]["runtime"] == "threejs"


# ---------------------------------------------------------------------------
# Factory + Protocol bridge shape
# ---------------------------------------------------------------------------


def test_ws_bridge_protocol_matches_fake_bridge() -> None:
    assert isinstance(FakeBridge(), WSBridge)


def test_factory_returns_adapter_with_null_bridge() -> None:
    from openmimicry.avatar.runtimes.threejs.adapter import make_threejs_avatar_adapter

    adapter = make_threejs_avatar_adapter()
    assert isinstance(adapter, ThreeJSAvatarAdapter)
