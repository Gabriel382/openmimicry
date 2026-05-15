"""openmimicry-core: contracts, schemas, EventBus, runtime, config, logging.

The cross-module **shape** lives here in ``contracts`` and ``schemas`` and is
frozen by ``docs/contracts.md``. The cross-module **runtime services**
(``EventBus``, ``Runtime``, ``AppConfig`` loader, structlog setup) live as
sibling modules in this package and are owned by M0.
"""

from __future__ import annotations

# Concrete EventBus + Runtime + RuntimeStore (M0 implementation).
from .bus import EventBus

# Contracts — the Protocols every adapter satisfies.
from .contracts import (
    AvatarDirector,
    AvatarOrchestrator,
    AvatarRuntimeAdapter,
    LLMAdapter,
    SpeechController,
    STTAdapter,
    TaskRuntimeAdapter,
    TTSAdapter,
    WakeController,
)
from .runtime import Runtime, create_runtime

# Schemas — the data shapes every module exchanges.
from .schemas import (
    SCHEMA_VERSION,
    AppConfig,
    Artifact,
    AvatarDirective,
    CharacterPack,
    ConfigUpdated,
    Emotion,
    EmotionFrames,
    ErrorEvent,
    LLMChunk,
    LLMMessage,
    LLMReplyComplete,
    LLMStarted,
    LLMTokenStreamed,
    LLMUsage,
    RuntimeEvent,
    RuntimeEventAdapter,
    State,
    STTConfig,
    TaskCompleted,
    TaskConstraints,
    TaskError,
    TaskHandle,
    TaskInput,
    TaskRequest,
    TaskResult,
    TaskStatus,
    TaskStatusName,
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
from .store import RuntimeStore

__all__ = [
    "SCHEMA_VERSION",
    # Schema data types
    "AppConfig",
    "Artifact",
    "AvatarDirective",
    # Protocols
    "AvatarDirector",
    "AvatarOrchestrator",
    "AvatarRuntimeAdapter",
    "CharacterPack",
    "ConfigUpdated",
    "Emotion",
    "EmotionFrames",
    "ErrorEvent",
    # Runtime classes
    "EventBus",
    "LLMAdapter",
    "LLMChunk",
    "LLMMessage",
    "LLMReplyComplete",
    "LLMStarted",
    "LLMTokenStreamed",
    "LLMUsage",
    "Runtime",
    "RuntimeEvent",
    "RuntimeEventAdapter",
    "RuntimeStore",
    "STTAdapter",
    "STTConfig",
    "SpeechController",
    "State",
    "TTSAdapter",
    "TTSChunkBoundary",
    "TTSChunkSpoken",
    "TTSConfig",
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
    "TaskRuntimeAdapter",
    "TaskStatus",
    "TaskStatusName",
    "TaskSubmitted",
    "TaskUpdate",
    "TaskUpdatedEvent",
    "ToolSpec",
    "Transcript",
    "TranscriptPreview",
    "UserSpeechFinal",
    "UserSpeechStarted",
    "UserTextSubmitted",
    "WakeController",
    "WakeDetected",
    "WakeEvent",
    "create_runtime",
]

__version__ = "0.2.0a0"
