"""Recording MockAvatarRuntimeAdapter — the canonical fixture.

Replaces the Phase 0 ``NotImplementedError`` stub. Every consumer (M6
backend integration tests, M4 Sprite2D unit tests, the contract suite,
and the M3 orchestrator unit tests themselves) drives this mock instead
of touching a real renderer.

The adapter accepts *any* well-formed :class:`AvatarDirective`, including
ones with ``gesture``/``gaze``/``intensity`` fields it doesn't understand
— it must not raise. Tests assert on :attr:`directives_received`,
:attr:`is_visible`, :attr:`is_speaking`, and :attr:`last_text`.
"""

from __future__ import annotations

from typing import Any

from openmimicry.core.schemas import AvatarDirective

__all__ = ["MockAvatarRuntimeAdapter", "make_mock_avatar_runtime_adapter"]


class MockAvatarRuntimeAdapter:
    """Recording :class:`AvatarRuntimeAdapter` — never raises."""

    name: str = "mock"

    def __init__(self) -> None:
        self.capabilities: set[str] = {"mock"}
        self.directives_received: list[AvatarDirective] = []
        self.is_visible: bool = True
        self.is_speaking: bool = False
        self.last_text: str | None = None
        self.loaded_character: str | None = None
        self.last_character_config: dict[str, Any] = {}
        self.load_calls: int = 0
        self.shutdown_calls: int = 0
        self._closed: bool = False

    async def load_character(self, character_id: str, config: dict[str, Any]) -> None:
        self.load_calls += 1
        self.loaded_character = character_id
        self.last_character_config = dict(config)

    async def apply_directive(self, directive: AvatarDirective) -> None:
        # Per the brief: must accept *any* well-formed directive without
        # raising, even one with fields the adapter doesn't understand.
        self.directives_received.append(directive)
        if directive.speaking:
            self.is_speaking = True
        elif directive.state != "speaking":
            self.is_speaking = False
        if directive.text is not None:
            self.last_text = directive.text

    async def set_text(self, text: str) -> None:
        self.last_text = text

    async def start_speaking(self, text: str | None = None) -> None:
        self.is_speaking = True
        if text is not None:
            self.last_text = text

    async def stop_speaking(self) -> None:
        self.is_speaking = False

    async def set_visibility(self, visible: bool) -> None:
        self.is_visible = visible

    async def healthcheck(self) -> bool:
        return not self._closed

    async def shutdown(self) -> None:
        self.shutdown_calls += 1
        self._closed = True


def make_mock_avatar_runtime_adapter(*_args: Any, **_kwargs: Any) -> MockAvatarRuntimeAdapter:
    """Entry-point factory used by the contract conftest."""
    return MockAvatarRuntimeAdapter()
