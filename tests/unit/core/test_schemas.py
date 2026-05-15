"""Phase 0 schema sanity tests.

These tests are intentionally exhaustive over the event union: a freeze that
forgets a variant will be caught here, not in production.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from openmimicry.core.schemas import (
    AppConfig,
    Artifact,
    AvatarDirective,
    CharacterPack,
    ConfigUpdated,
    EmotionFrames,
    ErrorEvent,
    LLMChunk,
    LLMMessage,
    LLMReplyComplete,
    LLMStarted,
    LLMTokenStreamed,
    LLMUsage,
    RuntimeEventAdapter,
    STTConfig,
    TaskCompleted,
    TaskHandle,
    TaskRequest,
    TaskResult,
    TaskSubmitted,
    TaskUpdate,
    TaskUpdatedEvent,
    ToolSpec,
    Transcript,
    TranscriptPreview,
    TTSChunkBoundary,
    TTSChunkSpoken,
    TTSConfig,
    TTSFinished,
    TTSInterrupted,
    TTSStarted,
    UserSpeechFinal,
    UserSpeechStarted,
    UserTextSubmitted,
    WakeDetected,
    WakeEvent,
)
from pydantic import ValidationError

_TS = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)
_HANDLE = TaskHandle(id="t1", runtime="mock")
_RESULT = TaskResult(handle=_HANDLE, status="succeeded")
_UPDATE = TaskUpdate(handle=_HANDLE, status="running", ts=_TS)


# ---------------------------------------------------------------------------
# Frozen
# ---------------------------------------------------------------------------


def test_avatar_directive_is_frozen() -> None:
    d = AvatarDirective(state="idle")
    with pytest.raises(ValidationError):
        d.state = "speaking"  # type: ignore[misc]


def test_app_config_is_frozen() -> None:
    cfg = AppConfig()
    with pytest.raises(ValidationError):
        cfg.schema_version = 99  # type: ignore[misc]


def test_app_config_forbids_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        AppConfig.model_validate({"unknown": True})


# ---------------------------------------------------------------------------
# Round-trip every event variant
# ---------------------------------------------------------------------------


EVENT_INSTANCES = [
    UserTextSubmitted(ts=_TS, text="hello"),
    UserSpeechStarted(ts=_TS),
    UserSpeechFinal(ts=_TS, text="done", reason="normal"),
    TranscriptPreview(ts=_TS, text="part", is_final=False),
    WakeDetected(ts=_TS, name="Mimi"),
    LLMStarted(ts=_TS),
    LLMTokenStreamed(ts=_TS, delta="hi"),
    LLMReplyComplete(ts=_TS, full_text="hello world"),
    TTSStarted(ts=_TS),
    TTSChunkSpoken(ts=_TS),
    TTSFinished(ts=_TS),
    TTSInterrupted(ts=_TS),
    TaskSubmitted(ts=_TS, handle=_HANDLE, summary="job"),
    TaskUpdatedEvent(ts=_TS, update=_UPDATE),
    TaskCompleted(ts=_TS, handle=_HANDLE, result=_RESULT),
    ConfigUpdated(ts=_TS, diff={"app": {"log_level": "DEBUG"}}),
    ErrorEvent(ts=_TS, where="llm", message="boom", recoverable=True),
]


@pytest.mark.parametrize("event", EVENT_INSTANCES, ids=lambda e: e.kind)
def test_event_round_trips_via_json(event) -> None:
    payload = event.model_dump(mode="json")
    parsed = RuntimeEventAdapter.validate_python(payload)
    assert parsed.kind == event.kind
    assert type(parsed) is type(event)


def test_runtime_event_discriminator_resolves_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        RuntimeEventAdapter.validate_python({"kind": "not_a_real_event", "ts": _TS.isoformat()})


def test_runtime_event_round_trips_via_json_string() -> None:
    event = UserTextSubmitted(ts=_TS, text="hi")
    raw = json.dumps(event.model_dump(mode="json"))
    parsed = RuntimeEventAdapter.validate_json(raw)
    assert isinstance(parsed, UserTextSubmitted)
    assert parsed.text == "hi"


# ---------------------------------------------------------------------------
# LLM / voice / avatar / tasks leaves
# ---------------------------------------------------------------------------


def test_llm_message_validates_role() -> None:
    LLMMessage(role="user", content="hi")
    with pytest.raises(ValidationError):
        LLMMessage(role="nope", content="hi")  # type: ignore[arg-type]


def test_llm_chunk_defaults() -> None:
    chunk = LLMChunk()
    assert chunk.delta == ""
    assert chunk.role == "assistant"
    assert chunk.finish_reason is None
    assert chunk.tool_calls == []


def test_tool_spec_round_trip() -> None:
    spec = ToolSpec(name="fs.read", description="read file", parameters={"type": "object"})
    again = ToolSpec.model_validate_json(spec.model_dump_json())
    assert again == spec


def test_llm_usage_defaults_are_zero() -> None:
    usage = LLMUsage()
    assert usage.prompt_tokens == 0
    assert usage.completion_tokens == 0
    assert usage.total_tokens == 0


def test_voice_configs_defaults() -> None:
    stt = STTConfig()
    assert stt.language == "en"
    assert stt.vad == "silero"
    tts = TTSConfig()
    assert tts.engine == "coqui"
    assert tts.interruptible is True


def test_transcript_round_trip() -> None:
    t = Transcript(text="hi", is_final=True, confidence=0.9)
    assert Transcript.model_validate(t.model_dump()) == t


def test_wake_event_round_trip() -> None:
    w = WakeEvent(name="Mimi", confidence=0.7)
    assert WakeEvent.model_validate(w.model_dump()) == w


def test_tts_chunk_boundary_round_trip() -> None:
    b = TTSChunkBoundary(bytes_played=1024, timestamp_ms=500)
    assert TTSChunkBoundary.model_validate(b.model_dump()) == b


def test_emotion_frames_defaults() -> None:
    ef = EmotionFrames(frames="some/path")
    assert ef.fps == 10
    assert ef.loop is True


def test_character_pack_defaults() -> None:
    pack = CharacterPack(id="x", name="X")
    assert pack.kind == "sprite2d"
    assert pack.default_state == "idle"
    assert pack.default_emotion == "neutral"


def test_task_request_defaults() -> None:
    req = TaskRequest(summary="s", instructions="i")
    assert req.inputs == []
    assert req.capabilities_required == set()
    assert req.constraints.network is True


def test_artifact_round_trip() -> None:
    a = Artifact(name="out.txt", mime="text/plain", path="/tmp/out.txt")
    assert Artifact.model_validate(a.model_dump()) == a


# ---------------------------------------------------------------------------
# AppConfig deep defaults
# ---------------------------------------------------------------------------


def test_app_config_default_tree_is_complete() -> None:
    cfg = AppConfig()
    assert cfg.schema_version == 1
    assert cfg.app.log_level == "INFO"
    assert cfg.app.log_format == "json"
    assert cfg.llm.adapter == "litellm"
    assert cfg.voice.stt.adapter == "realtimestt"
    assert cfg.voice.tts.engine == "coqui"
    assert cfg.avatar.runtime == "sprite2d"
    assert cfg.tasks.default_runtime == "mcp_agent"
    assert cfg.ui.overlay.click_through_default is True


def test_app_config_round_trips_to_dict() -> None:
    cfg = AppConfig()
    again = AppConfig.model_validate(cfg.model_dump())
    assert again == cfg
