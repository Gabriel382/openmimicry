"""Unit tests for ``Live3DAvatarAdapter``.

Same shape as the Three.js test suite — a ``FakeBridge`` records every
publish so we can assert exact wire payloads. The pack-load path drives
``tests/fixtures/packs/good_pack`` to keep the suite hermetic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openmimicry.avatar.runtimes.live3d.adapter import (
    Live3DAvatarAdapter,
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
    assert isinstance(Live3DAvatarAdapter(), AvatarRuntimeAdapter)


def test_runtime_name_and_capabilities() -> None:
    adapter = Live3DAvatarAdapter()
    assert adapter.name == "live3d"
    assert {"3d", "mouth", "procedural_idle"} <= adapter.capabilities


def test_ws_bridge_protocol_satisfied_by_fake() -> None:
    assert isinstance(FakeBridge(), WSBridge)


# ---------------------------------------------------------------------------
# Dispatch behaviour
# ---------------------------------------------------------------------------


async def test_apply_directive_publishes_live3d_projection() -> None:
    bridge = FakeBridge()
    adapter = Live3DAvatarAdapter(pack=_pack(), ws_bridge=bridge)
    await adapter.apply_directive(
        AvatarDirective(state="speaking", emotion="happy", speaking=True, intensity=0.6)
    )
    assert len(bridge.published) == 1
    msg = bridge.published[0]
    assert msg["runtime"] == "live3d"
    assert "live" in msg
    assert msg["live"]["mouth_driver"] == "amplitude"


async def test_runtime_cfg_disables_procedural_idle() -> None:
    bridge = FakeBridge()
    adapter = Live3DAvatarAdapter(
        pack=_pack(),
        ws_bridge=bridge,
        runtime_cfg={"procedural_idle": False, "mouth_driver": "off"},
    )
    await adapter.apply_directive(AvatarDirective(state="idle"))
    live = bridge.published[0]["live"]
    assert live["procedural_idle"] is False
    assert live["mouth_driver"] == "off"
    assert "amplitude" not in live
    assert "idle" not in live


async def test_apply_directive_without_pack_drops_quietly() -> None:
    bridge = FakeBridge()
    adapter = Live3DAvatarAdapter(ws_bridge=bridge)
    await adapter.apply_directive(AvatarDirective(state="idle"))
    assert bridge.published == []


async def test_apply_directive_never_raises_on_unknown_gesture() -> None:
    bridge = FakeBridge()
    adapter = Live3DAvatarAdapter(pack=_pack(), ws_bridge=bridge)
    await adapter.apply_directive(
        AvatarDirective(state="idle", gesture="not-a-real-gesture")
    )
    assert len(bridge.published) == 1
    assert "gestureClip" not in bridge.published[0]


async def test_bridge_errors_dont_propagate() -> None:
    class BoomBridge:
        async def publish(self, message):  # noqa: ANN001
            raise RuntimeError("network down")

    adapter = Live3DAvatarAdapter(pack=_pack(), ws_bridge=BoomBridge())
    # Must not raise.
    await adapter.apply_directive(AvatarDirective(state="idle"))


async def test_start_stop_speaking_emit_quick_toggles() -> None:
    bridge = FakeBridge()
    adapter = Live3DAvatarAdapter(pack=_pack(), ws_bridge=bridge)
    await adapter.start_speaking("hi")
    await adapter.stop_speaking()
    assert bridge.published[0]["runtime"] == "live3d"
    assert bridge.published[0]["speaking"] is True
    assert bridge.published[1]["speaking"] is False


async def test_set_text_and_visibility_emit_system_messages() -> None:
    bridge = FakeBridge()
    adapter = Live3DAvatarAdapter(pack=_pack(), ws_bridge=bridge)
    await adapter.set_text("hello")
    await adapter.set_visibility(False)
    assert bridge.published[0] == {"type": "bubble.text", "text": "hello", "complete": True}
    last = bridge.published[-1]
    assert last["type"] == "system.notice"
    assert last["visible"] is False


async def test_healthcheck_and_shutdown_are_idempotent() -> None:
    adapter = Live3DAvatarAdapter()
    assert await adapter.healthcheck() is True
    await adapter.shutdown()
    assert await adapter.healthcheck() is False
    # Double shutdown must be a no-op.
    await adapter.shutdown()


# ---------------------------------------------------------------------------
# Pack-load path
# ---------------------------------------------------------------------------


async def test_load_character_warns_on_non_3d_kind_but_still_loads() -> None:
    bridge = FakeBridge()
    adapter = Live3DAvatarAdapter(ws_bridge=bridge)
    await adapter.load_character(
        "good_pack", {"pack_path": str(FIXTURES / "good_pack")}
    )
    # First publish is the idle directive applied during load_character.
    assert len(bridge.published) == 1
    assert bridge.published[0]["runtime"] == "live3d"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_factory_returns_adapter_with_null_bridge() -> None:
    from openmimicry.avatar.runtimes.live3d.adapter import make_live3d_avatar_adapter

    adapter = make_live3d_avatar_adapter()
    assert isinstance(adapter, Live3DAvatarAdapter)
