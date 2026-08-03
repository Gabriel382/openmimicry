from __future__ import annotations

from pathlib import Path
from typing import Any

from openmimicry_backend.routes.dashboard import dashboard, dashboard_css, dashboard_js
from openmimicry_backend.ws import BroadcastBridge


class _Socket:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def send_json(self, message: dict[str, Any]) -> None:
        self.messages.append(message)


async def test_dashboard_assets_exist_and_are_served_with_expected_types() -> None:
    html = await dashboard()
    css = await dashboard_css()
    js = await dashboard_js()

    assert Path(html.path).is_file()
    assert Path(css.path).is_file()
    assert Path(js.path).is_file()
    assert html.media_type == "text/html"
    assert css.media_type == "text/css"
    assert js.media_type == "text/javascript"


def test_dashboard_exposes_configurable_name_gated_wake_listening() -> None:
    html_path = (
        Path(__file__).resolve().parents[3]
        / "apps/backend/src/openmimicry_backend/static/dashboard.html"
    )
    text = html_path.read_text(encoding="utf-8")
    assert "Wake listen" in text
    assert 'id="wake-name"' in text
    assert "begins with the configured name" in text
    assert 'id="conversation-history"' in text
    assert 'id="voice-result"' in text
    assert 'id="speech-pause"' in text
    assert "End-of-speech pause" in text
    assert 'href="/diagnostics/bundle"' in text


def test_dashboard_exposes_v16_configuration_surfaces() -> None:
    html_path = (
        Path(__file__).resolve().parents[3]
        / "apps/backend/src/openmimicry_backend/static/dashboard.html"
    )
    text = html_path.read_text(encoding="utf-8")
    for element_id in (
        "presentation-mode",
        "llm-backend",
        "llm-model-select",
        "personality-prompt",
        "memory-enabled",
        "memory-provider",
        "memory-extraction",
        "voice-clone-form",
        "voice-token-form",
        "pack-create-form",
        "threejs-transform-form",
        "threejs-animation-speed",
        "notifications-section",
        "task-runtime-status",
        "refresh-task-runtime",
    ):
        assert f'id="{element_id}"' in text


def test_dashboard_prevents_invalid_enabled_memory_provider_pair() -> None:
    root = Path(__file__).resolve().parents[3]
    html = (root / "apps/backend/src/openmimicry_backend/static/dashboard.html").read_text(
        encoding="utf-8"
    )
    javascript = (root / "apps/backend/src/openmimicry_backend/static/dashboard.js").read_text(
        encoding="utf-8"
    )

    assert "None (memory off)" in html
    assert "Turning memory on defaults to private Local SQLite storage." in html
    assert 'provider.value = "local"' in javascript
    assert 'enabled.value = "false"' in javascript
    assert 'throw new Error("Select Local SQLite or Hindsight' in javascript


async def test_late_dashboard_receives_the_latest_task_card() -> None:
    bridge = BroadcastBridge()
    await bridge.publish(
        {
            "type": "task.card",
            "update": {
                "handle": {"id": "task-1", "runtime": "mock"},
                "status": "running",
                "note": "working",
            },
        }
    )
    await bridge.publish(
        {
            "type": "task.card",
            "update": {
                "handle": {"id": "task-1", "runtime": "mock"},
                "status": "succeeded",
                "note": "done",
            },
        }
    )

    socket = _Socket()
    await bridge.add_socket(socket)  # type: ignore[arg-type]

    assert len(socket.messages) == 1
    assert socket.messages[0]["update"]["status"] == "succeeded"


async def test_late_dashboard_receives_deduplicated_conversation_history() -> None:
    bridge = BroadcastBridge()
    turn = {
        "type": "conversation.turn",
        "id": "speech_final:2026-01-01T00:00:00+00:00",
        "role": "user",
        "source": "voice",
        "text": "What time is it?",
        "ts": "2026-01-01T00:00:00+00:00",
    }
    await bridge.remember(turn)
    await bridge.remember(turn)

    socket = _Socket()
    await bridge.add_socket(socket)  # type: ignore[arg-type]

    assert socket.messages == [turn]


async def test_new_turn_reset_does_not_replay_an_incomplete_bubble() -> None:
    bridge = BroadcastBridge()
    await bridge.remember({"type": "bubble.text", "text": "old complete", "complete": True})
    await bridge.remember({"type": "bubble.text", "text": "", "complete": False, "reset": True})

    socket = _Socket()
    await bridge.add_socket(socket)  # type: ignore[arg-type]

    assert socket.messages == []
