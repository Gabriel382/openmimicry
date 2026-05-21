"""RuntimeStore unit tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from openmimicry.core.schemas.avatar import AvatarDirective
from openmimicry.core.schemas.events import (
    ConfigUpdated,
    LLMReplyComplete,
    TaskCompleted,
    TaskSubmitted,
    TaskUpdatedEvent,
    TTSFinished,
    TTSStarted,
    UserSpeechFinal,
    UserTextSubmitted,
    WakeDetected,
)
from openmimicry.core.schemas.tasks import TaskHandle, TaskResult, TaskUpdate
from openmimicry.core.store import RuntimeStore
from pydantic import ValidationError


def _ts() -> datetime:
    return datetime.now(timezone.utc)


def test_default_store_is_empty() -> None:
    s = RuntimeStore()
    assert s.last_user_text is None
    assert s.last_assistant_text is None
    assert s.is_speaking is False
    assert s.live_wake_enabled is False
    assert s.active_tasks == {}
    assert s.current_directive is None


def test_store_is_frozen() -> None:
    s = RuntimeStore()
    with pytest.raises(ValidationError):
        s.is_speaking = True  # type: ignore[misc]


def test_update_returns_new_instance() -> None:
    s = RuntimeStore()
    s2 = s.update(UserTextSubmitted(ts=_ts(), text="hi"))
    assert s.last_user_text is None  # original unchanged
    assert s2.last_user_text == "hi"
    assert s is not s2


def test_user_speech_final_normal_updates_text() -> None:
    s = RuntimeStore()
    s2 = s.update(UserSpeechFinal(ts=_ts(), text="hi", reason="normal"))
    assert s2.last_user_text == "hi"
    # Other reasons do not update.
    s3 = s.update(UserSpeechFinal(ts=_ts(), text="x", reason="no_speech"))
    assert s3.last_user_text is None


def test_llm_reply_updates_assistant_text() -> None:
    s = RuntimeStore()
    s2 = s.update(LLMReplyComplete(ts=_ts(), full_text="hello world"))
    assert s2.last_assistant_text == "hello world"


def test_tts_lifecycle_toggles_is_speaking() -> None:
    s = RuntimeStore()
    s = s.update(TTSStarted(ts=_ts()))
    assert s.is_speaking is True
    s = s.update(TTSFinished(ts=_ts()))
    assert s.is_speaking is False


def test_wake_detected_toggles_live_wake() -> None:
    s = RuntimeStore()
    s = s.update(WakeDetected(ts=_ts(), name="Mimi"))
    assert s.live_wake_enabled is True


def test_task_lifecycle_populates_active_tasks() -> None:
    handle = TaskHandle(id="t1", runtime="mock")
    s = RuntimeStore()
    s = s.update(TaskSubmitted(ts=_ts(), handle=handle, summary="do it"))
    assert "t1" in s.active_tasks
    assert s.active_tasks["t1"].status == "queued"

    upd = TaskUpdate(handle=handle, status="running", ts=_ts())
    s = s.update(TaskUpdatedEvent(ts=_ts(), update=upd))
    assert s.active_tasks["t1"].status == "running"

    result = TaskResult(handle=handle, status="succeeded")
    s = s.update(TaskCompleted(ts=_ts(), handle=handle, result=result))
    assert s.active_tasks["t1"].status == "succeeded"


def test_config_updated_toggles_live_wake_when_diff_says_so() -> None:
    s = RuntimeStore()
    s = s.update(ConfigUpdated(ts=_ts(), diff={"voice": {"modes": {"live_wake": True}}}))
    assert s.live_wake_enabled is True


def test_unknown_event_returns_self() -> None:
    s = RuntimeStore()
    # ConfigUpdated with no live_wake diff is a no-op.
    s2 = s.update(ConfigUpdated(ts=_ts(), diff={"app": {"log_level": "DEBUG"}}))
    assert s2 is s


def test_with_directive_sets_current_and_speaking() -> None:
    s = RuntimeStore()
    d = AvatarDirective(state="speaking", speaking=True)
    s2 = s.with_directive(d)
    assert s2.current_directive == d
    assert s2.is_speaking is True

    quiet = AvatarDirective(state="idle", speaking=False)
    s3 = s2.with_directive(quiet)
    assert s3.current_directive == quiet
    # ``with_directive`` only flips is_speaking when speaking=True; cleanup
    # of is_speaking is the TTS-lifecycle event's job.
    assert s3.is_speaking is True
