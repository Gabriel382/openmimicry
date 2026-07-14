"""Unit tests for Sprite2DAvatarAdapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from openmimicry.avatar.pack import load_pack
from openmimicry.avatar.runtimes.sprite2d.adapter import (
    Sprite2DAvatarAdapter,
    WSBridge,
)
from openmimicry.core.contracts import AvatarRuntimeAdapter
from openmimicry.core.schemas import AvatarDirective

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "packs"


class FakeBridge:
    """Records every publish() call. Implements the WSBridge protocol."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.fail_next: bool = False

    async def publish(self, message: dict[str, Any]) -> None:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("bridge transport error")
        self.messages.append(message)


@pytest.fixture
def pack():
    return load_pack(FIXTURES / "good_pack")


def test_sprite2d_satisfies_avatar_runtime_protocol(pack) -> None:
    adapter = Sprite2DAvatarAdapter(pack=pack)
    assert isinstance(adapter, AvatarRuntimeAdapter)


def test_bridge_protocol_isinstance() -> None:
    assert isinstance(FakeBridge(), WSBridge)


async def test_apply_directive_publishes_projection(pack) -> None:
    bridge = FakeBridge()
    adapter = Sprite2DAvatarAdapter(pack=pack, ws_bridge=bridge)
    await adapter.apply_directive(AvatarDirective(state="idle", speaking=False))
    assert len(bridge.messages) == 1
    msg = bridge.messages[0]
    assert msg["type"] == "avatar.directive"
    assert msg["runtime"] == "sprite2d"
    assert msg["fps"] == 8
    assert len(msg["frames"]) == 2


async def test_apply_directive_ignores_unsupported_fields(pack) -> None:
    """Sprite2D does not render gesture/gaze/intensity; must not raise."""
    bridge = FakeBridge()
    adapter = Sprite2DAvatarAdapter(pack=pack, ws_bridge=bridge)
    await adapter.apply_directive(
        AvatarDirective(
            state="happy",
            emotion="happy",
            gesture="wave",
            gaze="left",
            intensity=0.7,
        )
    )
    assert len(bridge.messages) == 1
    # The directive field round-trips through the projection.
    assert bridge.messages[0]["directive"]["gesture"] == "wave"


async def test_apply_directive_speaking_uses_speaking_frames(pack) -> None:
    bridge = FakeBridge()
    adapter = Sprite2DAvatarAdapter(pack=pack, ws_bridge=bridge)
    await adapter.apply_directive(AvatarDirective(state="idle", speaking=True))
    assert any("idle_speaking" in f for f in bridge.messages[0]["frames"])


async def test_unknown_state_falls_back_and_warns_once(
    pack, caplog: pytest.LogCaptureFixture
) -> None:
    bridge = FakeBridge()
    adapter = Sprite2DAvatarAdapter(pack=pack, ws_bridge=bridge)
    with caplog.at_level("WARNING"):
        await adapter.apply_directive(AvatarDirective(state="thinking"))
        await adapter.apply_directive(AvatarDirective(state="thinking"))
        await adapter.apply_directive(AvatarDirective(state="thinking"))
    # Two publishes succeeded (fell back to default_state) -- adapter never raised.
    assert len(bridge.messages) == 3
    warns = [r for r in caplog.records if "not in pack" in r.getMessage()]
    assert len(warns) == 1  # Warned ONCE per unknown state.


async def test_apply_directive_without_pack_drops_silently(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bridge = FakeBridge()
    adapter = Sprite2DAvatarAdapter(pack=None, ws_bridge=bridge)
    with caplog.at_level("WARNING"):
        await adapter.apply_directive(AvatarDirective(state="idle"))
    assert bridge.messages == []
    assert any("without a loaded pack" in r.getMessage() for r in caplog.records)


async def test_bridge_publish_error_is_logged_not_raised(
    pack, caplog: pytest.LogCaptureFixture
) -> None:
    bridge = FakeBridge()
    bridge.fail_next = True
    adapter = Sprite2DAvatarAdapter(pack=pack, ws_bridge=bridge)
    with caplog.at_level("WARNING"):
        # Must not raise even though the bridge errors.
        await adapter.apply_directive(AvatarDirective(state="idle"))
    assert bridge.messages == []
    assert any("bridge.publish failed" in r.getMessage() for r in caplog.records)


async def test_set_text_publishes_bubble(pack) -> None:
    bridge = FakeBridge()
    adapter = Sprite2DAvatarAdapter(pack=pack, ws_bridge=bridge)
    await adapter.set_text("hello world")
    assert bridge.messages[-1] == {
        "type": "bubble.text",
        "text": "hello world",
        "complete": True,
    }


async def test_start_stop_speaking(pack) -> None:
    bridge = FakeBridge()
    adapter = Sprite2DAvatarAdapter(pack=pack, ws_bridge=bridge)
    await adapter.start_speaking(text="hi")
    await adapter.stop_speaking()
    assert bridge.messages[0]["speaking"] is True
    assert bridge.messages[0]["text"] == "hi"
    assert bridge.messages[1]["speaking"] is False


async def test_set_visibility(pack) -> None:
    bridge = FakeBridge()
    adapter = Sprite2DAvatarAdapter(pack=pack, ws_bridge=bridge)
    await adapter.set_visibility(False)
    msg = bridge.messages[-1]
    assert msg["type"] == "system.notice"
    assert msg["visible"] is False


async def test_load_character_swaps_pack(tmp_path: Path) -> None:
    # Build a tiny pack on disk so load_character can find it.
    pack_dir = tmp_path / "mini"
    (pack_dir / "states" / "idle").mkdir(parents=True)
    (pack_dir / "states" / "idle" / "0.png").write_bytes(b"")
    (pack_dir / "pack.yaml").write_text(
        "schema_version: 1\nid: mini\nname: Mini\n"
        "emotions:\n  idle:\n    frames: states/idle\n    fps: 8\n",
        encoding="utf-8",
    )

    bridge = FakeBridge()
    adapter = Sprite2DAvatarAdapter(ws_bridge=bridge)
    await adapter.load_character("mini", {"pack_path": str(pack_dir)})
    # A fresh idle directive is auto-emitted after loading.
    assert any(m.get("directive", {}).get("state") == "idle" for m in bridge.messages)


async def test_healthcheck_and_shutdown(pack) -> None:
    adapter = Sprite2DAvatarAdapter(pack=pack)
    assert await adapter.healthcheck() is True
    await adapter.shutdown()
    assert await adapter.healthcheck() is False
    # Idempotent.
    await adapter.shutdown()
