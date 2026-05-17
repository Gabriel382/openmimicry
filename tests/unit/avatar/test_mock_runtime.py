"""Unit tests for MockAvatarRuntimeAdapter."""

from __future__ import annotations

import pytest
from openmimicry.avatar.mocks import MockAvatarRuntimeAdapter
from openmimicry.core.contracts import AvatarRuntimeAdapter
from openmimicry.core.schemas import AvatarDirective


def test_mock_satisfies_protocol() -> None:
    assert isinstance(MockAvatarRuntimeAdapter(), AvatarRuntimeAdapter)


async def test_records_directives_in_order() -> None:
    rt = MockAvatarRuntimeAdapter()
    d1 = AvatarDirective(state="idle")
    d2 = AvatarDirective(state="listening")
    d3 = AvatarDirective(state="speaking", speaking=True)
    await rt.apply_directive(d1)
    await rt.apply_directive(d2)
    await rt.apply_directive(d3)
    assert [d.state for d in rt.directives_received] == ["idle", "listening", "speaking"]


async def test_apply_directive_accepts_unknown_fields() -> None:
    """Per the brief: must not raise on gesture/gaze/intensity."""
    rt = MockAvatarRuntimeAdapter()
    await rt.apply_directive(
        AvatarDirective(
            state="happy",
            emotion="happy",
            gesture="wave",
            gaze="left",
            intensity=0.8,
        )
    )
    assert rt.directives_received[-1].gesture == "wave"


async def test_speaking_flag_tracks_directive() -> None:
    rt = MockAvatarRuntimeAdapter()
    assert rt.is_speaking is False
    await rt.apply_directive(AvatarDirective(state="speaking", speaking=True))
    assert rt.is_speaking is True
    await rt.apply_directive(AvatarDirective(state="idle", speaking=False))
    assert rt.is_speaking is False


async def test_text_propagation() -> None:
    rt = MockAvatarRuntimeAdapter()
    await rt.apply_directive(AvatarDirective(state="speaking", speaking=True, text="hi"))
    assert rt.last_text == "hi"
    await rt.set_text("explicit")
    assert rt.last_text == "explicit"


async def test_load_character_records_args() -> None:
    rt = MockAvatarRuntimeAdapter()
    await rt.load_character("octomimic", {"foo": "bar"})
    assert rt.loaded_character == "octomimic"
    assert rt.last_character_config == {"foo": "bar"}
    assert rt.load_calls == 1


async def test_visibility_toggle() -> None:
    rt = MockAvatarRuntimeAdapter()
    assert rt.is_visible is True
    await rt.set_visibility(False)
    assert rt.is_visible is False


async def test_shutdown_flips_healthcheck() -> None:
    rt = MockAvatarRuntimeAdapter()
    assert await rt.healthcheck() is True
    await rt.shutdown()
    assert await rt.healthcheck() is False
    assert rt.shutdown_calls == 1
