"""Frozen Pydantic v2 schemas for every cross-module data type.

Schemas in this package are the runtime mirror of ``docs/contracts.md`` §2–§7.
They are immutable and may only change through the contract-change procedure
documented in §11 of that file.
"""

from __future__ import annotations

from .app import (
    SCHEMA_VERSION,
    AppConfig,
    AppRuntimeConfig,
    AvatarConfig,
    HotkeysConfig,
    LLMConfig,
    LLMFallbackConfig,
    LLMRetryConfig,
    OverlayConfig,
    PanelConfig,
    STTConfigSection,
    STTWakeConfig,
    TaskRuntimeConfigEntry,
    TasksConfig,
    TrayConfig,
    TTSConfigSection,
    UIConfig,
    VoiceConfig,
    VoiceModesConfig,
)
from .avatar import AvatarDirective, CharacterPack, Emotion, EmotionFrames, State
from .events import (
    ConfigUpdated,
    ErrorEvent,
    LLMReplyComplete,
    LLMStarted,
    LLMTokenStreamed,
    RuntimeEvent,
    RuntimeEventAdapter,
    TaskCompleted,
    TaskSubmitted,
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
from .llm import LLMChunk, LLMMessage, LLMUsage, ToolSpec
from .tasks import (
    Artifact,
    TaskConstraints,
    TaskError,
    TaskHandle,
    TaskInput,
    TaskRequest,
    TaskResult,
    TaskStatus,
    TaskStatusName,
    TaskUpdate,
)
from .voice import STTConfig, Transcript, TTSChunkBoundary, TTSConfig, WakeEvent

__all__ = [
    "SCHEMA_VERSION",
    # app
    "AppConfig",
    "AppRuntimeConfig",
    # tasks
    "Artifact",
    "AvatarConfig",
    # avatar
    "AvatarDirective",
    "CharacterPack",
    # events
    "ConfigUpdated",
    "Emotion",
    "EmotionFrames",
    "ErrorEvent",
    "HotkeysConfig",
    # llm
    "LLMChunk",
    "LLMConfig",
    "LLMFallbackConfig",
    "LLMMessage",
    "LLMReplyComplete",
    "LLMRetryConfig",
    "LLMStarted",
    "LLMTokenStreamed",
    "LLMUsage",
    "OverlayConfig",
    "PanelConfig",
    "RuntimeEvent",
    "RuntimeEventAdapter",
    # voice
    "STTConfig",
    "STTConfigSection",
    "STTWakeConfig",
    "State",
    "TTSChunkBoundary",
    "TTSChunkSpoken",
    "TTSConfig",
    "TTSConfigSection",
    "TTSFinished",
    "TTSInterrupted",
    "TTSStarted",
    "TaskCompleted",
    "TaskConstraints",
    "TaskError",
    "TaskHandle",
    "TaskInput",
    "TaskRequest",
    "TaskResult",
    "TaskRuntimeConfigEntry",
    "TaskStatus",
    "TaskStatusName",
    "TaskSubmitted",
    "TaskUpdate",
    "TaskUpdatedEvent",
    "TasksConfig",
    "ToolSpec",
    "Transcript",
    "TranscriptPreview",
    "TrayConfig",
    "UIConfig",
    "UserSpeechFinal",
    "UserSpeechStarted",
    "UserTextSubmitted",
    "VoiceConfig",
    "VoiceModesConfig",
    "WakeDetected",
    "WakeEvent",
]
