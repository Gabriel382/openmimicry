"""Unit tests for WakeController."""

from __future__ import annotations

from openmimicry.core.schemas.app import STTConfigSection, STTWakeConfig
from openmimicry.voice.controllers.wake import WakeController
from openmimicry.voice.mocks import MockSTTAdapter


async def test_enable_starts_stt_in_wake_mode() -> None:
    stt = MockSTTAdapter()
    cfg = STTConfigSection(wake=STTWakeConfig(names=["Mimi", "Hey Mimi"]))
    ctl = WakeController(stt=stt, config=cfg)
    await ctl.enable()
    assert ctl.enabled is True
    assert stt.last_config is not None
    assert stt.last_config.mode == "wake"
    assert stt.last_config.wake_names == ["Mimi", "Hey Mimi"]


async def test_enable_is_idempotent() -> None:
    stt = MockSTTAdapter()
    ctl = WakeController(stt=stt)
    await ctl.enable()
    await ctl.enable()
    assert stt.start_calls == 1


async def test_disable_stops_stt() -> None:
    stt = MockSTTAdapter()
    ctl = WakeController(stt=stt)
    await ctl.enable()
    await ctl.disable()
    assert ctl.enabled is False
    assert stt.stop_calls == 1


async def test_disable_when_not_enabled_is_noop() -> None:
    stt = MockSTTAdapter()
    ctl = WakeController(stt=stt)
    await ctl.disable()
    assert stt.stop_calls == 0
