"""Unit-flavoured integration test for the projection mapping.

Each ``RuntimeEvent`` variant goes through :func:`projection.project` and
we assert the wire shape (or ``None``). This is the executable mirror of
``docs/contracts.md`` §9 — adding a new event kind must update either
:func:`project` or this test.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from openmimicry.core import (
    ConfigUpdated,
    ErrorEvent,
    LLMReplyComplete,
    LLMStarted,
    LLMTokenStreamed,
    TaskCompleted,
    TaskHandle,
    TaskResult,
    TaskSubmitted,
    TaskUpdate,
    TaskUpdatedEvent,
    TranscriptPreview,
    TTSChunkSpoken,
    TTSFinished,
    TTSInterrupted,
    TTSStarted,
    UserSpeechFinal,
    UserSpeechStarted,
    UserTextSubmitted,
    WakeDetected,
)
from openmimicry_backend.projection import project

pytestmark = pytest.mark.integration


def _ts() -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_transcript_preview_projects() -> None:
    out = project(TranscriptPreview(ts=_ts(), text="hi", is_final=False))
    assert out == {"type": "transcript.preview", "text": "hi", "is_final": False}


def test_llm_token_projects_bubble_partial() -> None:
    out = project(LLMTokenStreamed(ts=_ts(), delta="Hel"))
    assert out == {"type": "bubble.text", "text": "Hel", "complete": False}


def test_llm_reply_complete_projects_bubble_final() -> None:
    out = project(LLMReplyComplete(ts=_ts(), full_text="Hello"))
    assert out == {"type": "bubble.text", "text": "Hello", "complete": True}


def test_task_submitted_projects_task_card_queued() -> None:
    handle = TaskHandle(id="abc", runtime="mock")
    out = project(TaskSubmitted(ts=_ts(), handle=handle, summary="sum"))
    assert out is not None
    assert out["type"] == "task.card"
    assert out["update"]["handle"]["id"] == "abc"
    assert out["update"]["status"] == "queued"


def test_task_updated_event_projects_task_card() -> None:
    handle = TaskHandle(id="x", runtime="mock")
    upd = TaskUpdate(handle=handle, status="running", ts=_ts(), note="step")
    out = project(TaskUpdatedEvent(ts=_ts(), update=upd))
    assert out is not None
    assert out["type"] == "task.card"
    assert out["update"]["status"] == "running"
    assert out["update"]["note"] == "step"


def test_task_completed_projects_task_card_terminal() -> None:
    handle = TaskHandle(id="y", runtime="mock")
    result = TaskResult(handle=handle, status="succeeded", summary="done")
    out = project(TaskCompleted(ts=_ts(), handle=handle, result=result))
    assert out is not None
    assert out["type"] == "task.card"
    assert out["update"]["status"] == "succeeded"


def test_wake_projects_system_notice_info() -> None:
    out = project(WakeDetected(ts=_ts(), name="Mimi"))
    assert out is not None
    assert out["type"] == "system.notice"
    assert out["level"] == "info"
    assert "Mimi" in out["message"]


def test_tts_interrupted_projects_warn_notice() -> None:
    out = project(TTSInterrupted(ts=_ts()))
    assert out == {
        "type": "system.notice",
        "level": "warn",
        "message": "tts_interrupted",
    }


def test_config_updated_projects_info_notice_with_diff() -> None:
    out = project(ConfigUpdated(ts=_ts(), diff={"live_wake": True}))
    assert out is not None
    assert out["type"] == "system.notice"
    assert out["level"] == "info"
    assert out["diff"] == {"live_wake": True}


def test_error_event_projects_error_notice() -> None:
    out = project(
        ErrorEvent(ts=_ts(), where="backend.x", message="boom", recoverable=False)
    )
    assert out is not None
    assert out["type"] == "system.notice"
    assert out["level"] == "error"
    assert out["message"] == "boom"
    assert out["recoverable"] is False


@pytest.mark.parametrize(
    "event",
    [
        UserTextSubmitted(ts=_ts(), text="hi"),
        UserSpeechStarted(ts=_ts()),
        UserSpeechFinal(ts=_ts(), text="hi"),
        LLMStarted(ts=_ts()),
        TTSStarted(ts=_ts()),
        TTSChunkSpoken(ts=_ts()),
        TTSFinished(ts=_ts()),
    ],
)
def test_state_transition_events_are_suppressed(event) -> None:
    """These are emitted by the avatar runtime via avatar.directive, not here."""
    assert project(event) is None
