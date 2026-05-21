"""Unit tests for AvatarDirector — full state-machine table from
docs/character_packs.md §4.

| state \\ Event | UserSpeechStarted | LLMStarted | TTSStarted | TTSChunkSpoken | TTSFinished | Error | TaskCompleted |
| idle           | listening         | thinking   | speaking*  | —              | —           | error | happy         |
| listening      | —                 | thinking   | speaking*  | —              | —           | error | happy         |
| thinking       | listening         | —          | speaking*  | —              | idle        | error | happy         |
| speaking       | listening         | —          | —          | speaking*      | idle        | error | happy         |
| happy          | listening         | thinking   | speaking*  | —              | —           | error | —             |
| error          | listening         | thinking   | speaking*  | —              | —           | —     | —             |

A cell of "—" means ``director.on_event`` returns ``None``.
``speaking*`` means the resulting directive has ``speaking=True``.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from openmimicry.avatar.director import AvatarDirector
from openmimicry.core.schemas import (
    AvatarDirective,
    ErrorEvent,
    LLMReplyComplete,
    LLMStarted,
    State,
    TaskCompleted,
    TTSChunkSpoken,
    TTSFinished,
    TTSStarted,
    UserSpeechStarted,
)
from openmimicry.core.schemas.app import AvatarConfig
from openmimicry.core.schemas.tasks import TaskHandle, TaskResult


def _ts() -> datetime:
    return datetime.now(timezone.utc)


def _make_director(state: State = "idle") -> AvatarDirector:
    d = AvatarDirector(config=AvatarConfig(default_state=state))
    # Inject the prior state for table cells whose row is non-default.
    d._state = state  # type: ignore[attr-defined]
    return d


# ---------------------------------------------------------------------------
# Per-cell table. None means no directive emitted.
# ---------------------------------------------------------------------------

_HANDLE = TaskHandle(id="t", runtime="mock")
_RESULT = TaskResult(handle=_HANDLE, status="succeeded")

TABLE: list[tuple[State, str, object, State | None, bool]] = [
    # (prior_state, event_label, event_instance, expected_next_state_or_None, speaking)
    # ---- idle ----
    ("idle", "UserSpeechStarted", UserSpeechStarted(ts=_ts()), "listening", False),
    ("idle", "LLMStarted", LLMStarted(ts=_ts()), "thinking", False),
    ("idle", "TTSStarted", TTSStarted(ts=_ts()), "speaking", True),
    ("idle", "TTSChunkSpoken", TTSChunkSpoken(ts=_ts()), None, False),
    ("idle", "TTSFinished", TTSFinished(ts=_ts()), None, False),
    ("idle", "ErrorEvent", ErrorEvent(ts=_ts(), where="x", message="m"), "error", False),
    ("idle", "TaskCompleted", TaskCompleted(ts=_ts(), handle=_HANDLE, result=_RESULT), "happy", False),
    # ---- listening ----
    ("listening", "UserSpeechStarted", UserSpeechStarted(ts=_ts()), None, False),
    ("listening", "LLMStarted", LLMStarted(ts=_ts()), "thinking", False),
    ("listening", "TTSStarted", TTSStarted(ts=_ts()), "speaking", True),
    ("listening", "TTSChunkSpoken", TTSChunkSpoken(ts=_ts()), None, False),
    ("listening", "TTSFinished", TTSFinished(ts=_ts()), None, False),
    ("listening", "ErrorEvent", ErrorEvent(ts=_ts(), where="x", message="m"), "error", False),
    ("listening", "TaskCompleted", TaskCompleted(ts=_ts(), handle=_HANDLE, result=_RESULT), "happy", False),
    # ---- thinking ----
    ("thinking", "UserSpeechStarted", UserSpeechStarted(ts=_ts()), "listening", False),
    ("thinking", "LLMStarted", LLMStarted(ts=_ts()), None, False),
    ("thinking", "TTSStarted", TTSStarted(ts=_ts()), "speaking", True),
    ("thinking", "TTSChunkSpoken", TTSChunkSpoken(ts=_ts()), None, False),
    ("thinking", "TTSFinished", TTSFinished(ts=_ts()), "idle", False),
    ("thinking", "ErrorEvent", ErrorEvent(ts=_ts(), where="x", message="m"), "error", False),
    ("thinking", "TaskCompleted", TaskCompleted(ts=_ts(), handle=_HANDLE, result=_RESULT), "happy", False),
    # ---- speaking ----
    ("speaking", "UserSpeechStarted", UserSpeechStarted(ts=_ts()), "listening", False),
    ("speaking", "LLMStarted", LLMStarted(ts=_ts()), None, False),
    ("speaking", "TTSStarted", TTSStarted(ts=_ts()), None, False),
    ("speaking", "TTSChunkSpoken", TTSChunkSpoken(ts=_ts()), "speaking", True),
    ("speaking", "TTSFinished", TTSFinished(ts=_ts()), "idle", False),
    ("speaking", "ErrorEvent", ErrorEvent(ts=_ts(), where="x", message="m"), "error", False),
    ("speaking", "TaskCompleted", TaskCompleted(ts=_ts(), handle=_HANDLE, result=_RESULT), "happy", False),
    # ---- happy ----
    ("happy", "UserSpeechStarted", UserSpeechStarted(ts=_ts()), "listening", False),
    ("happy", "LLMStarted", LLMStarted(ts=_ts()), "thinking", False),
    ("happy", "TTSStarted", TTSStarted(ts=_ts()), "speaking", True),
    ("happy", "TTSChunkSpoken", TTSChunkSpoken(ts=_ts()), None, False),
    ("happy", "TTSFinished", TTSFinished(ts=_ts()), None, False),
    ("happy", "ErrorEvent", ErrorEvent(ts=_ts(), where="x", message="m"), "error", False),
    ("happy", "TaskCompleted", TaskCompleted(ts=_ts(), handle=_HANDLE, result=_RESULT), None, False),
    # ---- error ----
    ("error", "UserSpeechStarted", UserSpeechStarted(ts=_ts()), "listening", False),
    ("error", "LLMStarted", LLMStarted(ts=_ts()), "thinking", False),
    ("error", "TTSStarted", TTSStarted(ts=_ts()), "speaking", True),
    ("error", "TTSChunkSpoken", TTSChunkSpoken(ts=_ts()), None, False),
    ("error", "TTSFinished", TTSFinished(ts=_ts()), None, False),
    ("error", "ErrorEvent", ErrorEvent(ts=_ts(), where="x", message="m"), None, False),
    ("error", "TaskCompleted", TaskCompleted(ts=_ts(), handle=_HANDLE, result=_RESULT), None, False),
]


@pytest.mark.parametrize(
    "prior_state,event_label,event,expected_state,expected_speaking",
    TABLE,
    ids=[f"{row[0]}__{row[1]}" for row in TABLE],
)
def test_state_machine_table_cell(
    prior_state: State,
    event_label: str,
    event,
    expected_state: State | None,
    expected_speaking: bool,
) -> None:
    director = _make_director(prior_state)
    directive = director.on_event(event)
    if expected_state is None:
        assert directive is None, (
            f"({prior_state}, {event_label}) expected no-op, got {directive}"
        )
        # state should be unchanged.
        assert director.state == prior_state
    else:
        assert directive is not None, (
            f"({prior_state}, {event_label}) expected {expected_state}, got None"
        )
        assert directive.state == expected_state
        assert directive.speaking is expected_speaking
        assert director.state == expected_state


def test_happy_directive_carries_hold_and_return() -> None:
    director = AvatarDirector(config=AvatarConfig(celebration_ms=1500))
    directive = director.on_event(
        TaskCompleted(ts=_ts(), handle=_HANDLE, result=_RESULT)
    )
    assert directive is not None
    assert directive.state == "happy"
    assert directive.emotion == "happy"
    assert directive.next_state == "idle"
    assert directive.duration_ms == 1500


def test_error_directive_carries_hold_and_return() -> None:
    director = AvatarDirector(config=AvatarConfig(error_ms=900))
    directive = director.on_event(
        ErrorEvent(ts=_ts(), where="llm", message="boom")
    )
    assert directive is not None
    assert directive.state == "error"
    assert directive.emotion == "worried"
    assert directive.next_state == "idle"
    assert directive.duration_ms == 900


def test_apply_return_to_resets_state() -> None:
    director = _make_director("happy")
    directive = director.apply_return_to("idle")
    assert directive.state == "idle"
    assert directive.speaking is False
    assert director.state == "idle"


def test_text_propagation_from_llm_reply() -> None:
    """If the event carries text (full_text/text/delta), it surfaces on the directive."""
    director = _make_director("thinking")
    directive = director.on_event(LLMReplyComplete(ts=_ts(), full_text="hello"))
    # thinking + LLMReplyComplete -> idle, text should be present.
    assert directive is not None
    assert directive.state == "idle"
    assert directive.text == "hello"


def test_emotion_mapping_is_default_neutral_for_idle() -> None:
    director = AvatarDirector(
        config=AvatarConfig(default_state="thinking")
    )
    # Force a transition that yields "idle".
    director._state = "thinking"  # type: ignore[attr-defined]
    directive = director.on_event(TTSFinished(ts=_ts()))
    assert directive is not None
    assert directive.state == "idle"
    assert directive.emotion == "neutral"
