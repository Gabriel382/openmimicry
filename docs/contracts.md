# Contracts (the immutable interface set)

This document is the single source of truth for every cross-module boundary in OpenMimicry. It is **frozen** the moment Phase 0 lands. Any change to a signature, schema, or field requires a coordinated PR that updates this document, the matching code, the contract tests, and every consumer. Modules may not unilaterally change anything here.

Every module under `packages/*` imports from `openmimicry.core.contracts.*` and only from there. The contracts in this file ship as code at `packages/openmimicry-core/src/openmimicry/core/contracts/` and `packages/openmimicry-core/src/openmimicry/core/schemas/`. This document is the human-readable mirror.

Schema version: `1`. Any breaking change increments to `2` and ships with a migration note in `CHANGELOG.md`.

## 1. Top-level packages

```text
openmimicry.core.contracts
  llm.py            LLMAdapter
  voice.py          STTAdapter, TTSAdapter, SpeechController, WakeController
  tasks.py          TaskRuntimeAdapter
  avatar.py         AvatarRuntimeAdapter, AvatarDirector, AvatarOrchestrator

openmimicry.core.schemas
  events.py         RuntimeEvent union and variants
  llm.py            LLMMessage, LLMChunk, ToolSpec, LLMUsage
  voice.py          STTConfig, TTSConfig, Transcript, WakeEvent, TTSChunkBoundary
  tasks.py          TaskRequest, TaskHandle, TaskUpdate, TaskResult, TaskStatus
  avatar.py         AvatarDirective, State, Emotion, CharacterPack
  app.py            AppConfig (and every sub-config: LLMConfig, VoiceConfig, …)
```

All schemas are Pydantic v2, `frozen=True` by default.

## 2. Core schemas

### 2.1 `RuntimeEvent`

```python
# openmimicry.core.schemas.events
from typing import Literal, Union
from pydantic import BaseModel
from datetime import datetime

class _Event(BaseModel, frozen=True):
    ts: datetime

class UserTextSubmitted(_Event):
    kind: Literal["user_text"] = "user_text"
    text: str

class UserSpeechStarted(_Event):
    kind: Literal["speech_start"] = "speech_start"

class UserSpeechFinal(_Event):
    kind: Literal["speech_final"] = "speech_final"
    text: str
    reason: Literal["normal", "no_speech", "interrupted"] = "normal"

class TranscriptPreview(_Event):
    kind: Literal["transcript_preview"] = "transcript_preview"
    text: str
    is_final: bool = False

class WakeDetected(_Event):
    kind: Literal["wake"] = "wake"
    name: str

class LLMStarted(_Event):
    kind: Literal["llm_start"] = "llm_start"

class LLMTokenStreamed(_Event):
    kind: Literal["llm_token"] = "llm_token"
    delta: str

class LLMReplyComplete(_Event):
    kind: Literal["llm_done"] = "llm_done"
    full_text: str

class TTSStarted(_Event):
    kind: Literal["tts_start"] = "tts_start"

class TTSChunkSpoken(_Event):
    kind: Literal["tts_chunk"] = "tts_chunk"

class TTSFinished(_Event):
    kind: Literal["tts_done"] = "tts_done"

class TTSInterrupted(_Event):
    kind: Literal["tts_interrupted"] = "tts_interrupted"

class TaskSubmitted(_Event):
    kind: Literal["task_submitted"] = "task_submitted"
    handle: "TaskHandle"
    summary: str

class TaskUpdatedEvent(_Event):
    kind: Literal["task_update"] = "task_update"
    update: "TaskUpdate"

class TaskCompleted(_Event):
    kind: Literal["task_done"] = "task_done"
    handle: "TaskHandle"
    result: "TaskResult"

class ConfigUpdated(_Event):
    kind: Literal["config_update"] = "config_update"
    diff: dict

class ErrorEvent(_Event):
    kind: Literal["error"] = "error"
    where: str           # module name
    message: str
    recoverable: bool = True

RuntimeEvent = Union[
    UserTextSubmitted, UserSpeechStarted, UserSpeechFinal, TranscriptPreview,
    WakeDetected, LLMStarted, LLMTokenStreamed, LLMReplyComplete,
    TTSStarted, TTSChunkSpoken, TTSFinished, TTSInterrupted,
    TaskSubmitted, TaskUpdatedEvent, TaskCompleted, ConfigUpdated, ErrorEvent,
]
```

### 2.2 `EventBus`

```python
# openmimicry.core.contracts.bus  (this one is a concrete class, not a Protocol;
# it ships with openmimicry-core. Other modules import the instance.)
class EventBus:
    def publish(self, event: RuntimeEvent) -> None: ...
    def subscribe(self) -> "AsyncIterator[RuntimeEvent]": ...
    async def aclose(self) -> None: ...
```

### 2.3 `AvatarDirective`, `State`, `Emotion`

```python
# openmimicry.core.schemas.avatar
from typing import Literal, Any
from pydantic import BaseModel

State = Literal["idle", "listening", "thinking", "speaking", "happy", "error"]
Emotion = Literal[
    "neutral", "happy", "sad", "angry", "confused", "focused", "worried"
]

class AvatarDirective(BaseModel, frozen=True):
    state: State
    emotion: Emotion = "neutral"
    animation: str | None = None
    speaking: bool = False
    text: str | None = None
    next_state: State | None = None
    duration_ms: int | None = None
    intensity: float | None = None
    gesture: str | None = None
    gaze: str | None = None
    metadata: dict[str, Any] = {}
```

### 2.4 `CharacterPack`

```python
# openmimicry.core.schemas.avatar (cont.)
class EmotionFrames(BaseModel, frozen=True):
    frames: str | list[str]                # folder path or explicit list
    speaking_frames: str | list[str] | None = None
    fps: int = 10
    loop: bool = True
    return_to: State | None = None
    hold_ms: int | None = None

class CharacterPack(BaseModel, frozen=True):
    schema_version: int = 1
    id: str
    name: str
    author: str | None = None
    license: str | None = None
    preview: str | None = None
    default_state: State = "idle"
    default_emotion: Emotion = "neutral"
    transition_ms: int = 120
    kind: Literal["sprite2d", "advanced2d", "threejs", "vrm", "gltf", "unity", "external"] = "sprite2d"
    emotions: dict[State, EmotionFrames] = {}
    voice_hint: dict[str, str] = {}
    metadata: dict[str, Any] = {}
```

## 3. LLM contracts

```python
# openmimicry.core.schemas.llm
class LLMMessage(BaseModel, frozen=True):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: str | None = None
    name: str | None = None

class ToolSpec(BaseModel, frozen=True):
    name: str
    description: str
    parameters: dict     # JSON schema

class LLMUsage(BaseModel, frozen=True):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class LLMChunk(BaseModel, frozen=True):
    delta: str = ""
    role: Literal["assistant"] = "assistant"
    finish_reason: Literal["stop", "length", "tool_calls", "content_filter", None] = None
    tool_calls: list[dict] = []
    usage: LLMUsage | None = None

# openmimicry.core.contracts.llm
from typing import AsyncIterator, Protocol, Sequence, runtime_checkable

@runtime_checkable
class LLMAdapter(Protocol):
    name: str

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        stream: bool = True,
        tools: Sequence[ToolSpec] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]: ...

    async def healthcheck(self) -> bool: ...
    async def close(self) -> None: ...
```

## 4. Voice contracts

```python
# openmimicry.core.schemas.voice
class STTConfig(BaseModel, frozen=True):
    language: str = "en"
    mode: Literal["wake", "dictation"] = "dictation"
    wake_names: list[str] = []
    sample_rate: int = 16000
    vad: Literal["silero", "webrtc", "none"] = "silero"

class TTSConfig(BaseModel, frozen=True):
    engine: str = "coqui"
    voice: str = "en_female_1"
    rate: float = 1.0
    interruptible: bool = True

class Transcript(BaseModel, frozen=True):
    text: str
    is_final: bool
    confidence: float | None = None
    segments: list[dict] = []

class WakeEvent(BaseModel, frozen=True):
    name: str
    confidence: float | None = None

class TTSChunkBoundary(BaseModel, frozen=True):
    bytes_played: int
    timestamp_ms: int

# openmimicry.core.contracts.voice
@runtime_checkable
class STTAdapter(Protocol):
    name: str

    async def start(self, config: STTConfig) -> None: ...
    async def stop(self) -> None: ...
    @property
    def transcripts(self) -> AsyncIterator[Transcript]: ...
    @property
    def vad_active(self) -> bool: ...
    async def healthcheck(self) -> bool: ...

from typing import AsyncIterable, Callable

OnChunk = Callable[[TTSChunkBoundary], None]

@runtime_checkable
class TTSAdapter(Protocol):
    name: str

    async def speak(
        self,
        text_or_stream: str | AsyncIterable[str],
        *,
        config: TTSConfig,
        on_chunk: OnChunk | None = None,
    ) -> None: ...
    async def stop(self) -> None: ...
    @property
    def is_speaking(self) -> bool: ...
    async def healthcheck(self) -> bool: ...

class SpeechController(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def say(self, text_or_stream: str | AsyncIterable[str]) -> None: ...
    async def interrupt(self) -> None: ...
    async def ptt_down(self) -> None: ...
    async def ptt_up(self) -> None: ...
    async def enable_live_listening(self, *, wake_names: list[str] | None) -> None: ...
    async def disable_live_listening(self) -> None: ...

class WakeController(Protocol):
    async def enable(self) -> None: ...
    async def disable(self) -> None: ...
```

## 5. Avatar contracts

```python
# openmimicry.core.contracts.avatar
@runtime_checkable
class AvatarRuntimeAdapter(Protocol):
    name: str
    capabilities: set[str]    # e.g. {"2d","speaking_variants"} or {"3d","gestures","gaze"}

    async def load_character(self, character_id: str, config: dict) -> None: ...
    async def apply_directive(self, directive: AvatarDirective) -> None: ...
    async def set_text(self, text: str) -> None: ...
    async def start_speaking(self, text: str | None = None) -> None: ...
    async def stop_speaking(self) -> None: ...
    async def set_visibility(self, visible: bool) -> None: ...
    async def healthcheck(self) -> bool: ...
    async def shutdown(self) -> None: ...

class AvatarDirector(Protocol):
    """Translates RuntimeEvent into AvatarDirective. Stateless from the caller's
    perspective: side effects live on the orchestrator."""
    def on_event(self, event: RuntimeEvent) -> AvatarDirective | None: ...

class AvatarOrchestrator(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def swap_runtime(self, new_runtime: AvatarRuntimeAdapter) -> None: ...
```

## 6. Task contracts

```python
# openmimicry.core.schemas.tasks
class TaskInput(BaseModel, frozen=True):
    kind: Literal["file", "url", "text", "blob"]
    value: str
    mime: str | None = None

class TaskConstraints(BaseModel, frozen=True):
    timeout_s: int | None = None
    max_cost_usd: float | None = None
    working_dir: str | None = None
    network: bool = True

class TaskRequest(BaseModel, frozen=True):
    summary: str
    instructions: str
    inputs: list[TaskInput] = []
    capabilities_required: set[str] = set()
    preferred_runtime: str | None = None
    constraints: TaskConstraints = TaskConstraints()
    metadata: dict[str, Any] = {}

class TaskHandle(BaseModel, frozen=True):
    id: str
    runtime: str

TaskStatusName = Literal["queued", "running", "succeeded", "failed", "cancelled"]

class TaskError(BaseModel, frozen=True):
    code: str
    message: str

class Artifact(BaseModel, frozen=True):
    name: str
    mime: str
    path: str | None = None
    inline: str | None = None

class TaskStatus(BaseModel, frozen=True):
    handle: TaskHandle
    status: TaskStatusName
    note: str | None = None
    progress: float | None = None

class TaskUpdate(BaseModel, frozen=True):
    handle: TaskHandle
    status: TaskStatusName
    note: str | None = None
    progress: float | None = None
    stdout: str | None = None
    artifacts: list[Artifact] = []
    error: TaskError | None = None
    ts: datetime

class TaskResult(BaseModel, frozen=True):
    handle: TaskHandle
    status: TaskStatusName
    artifacts: list[Artifact] = []
    summary: str | None = None
    error: TaskError | None = None

# openmimicry.core.contracts.tasks
@runtime_checkable
class TaskRuntimeAdapter(Protocol):
    name: str
    capabilities: set[str]

    async def submit(self, req: TaskRequest) -> TaskHandle: ...
    async def status(self, handle: TaskHandle) -> TaskStatus: ...
    async def cancel(self, handle: TaskHandle) -> None: ...
    def updates(self, handle: TaskHandle) -> AsyncIterator[TaskUpdate]: ...
    async def result(self, handle: TaskHandle) -> TaskResult: ...
    async def healthcheck(self) -> bool: ...
```

## 7. AppConfig

The exhaustive shape is in [`configuration.md`](./configuration.md). The schema models live in `openmimicry.core.schemas.app` and are imported by every module that needs to read configuration. They are frozen the same way as the rest.

The top-level model exposes these typed sub-configs:

```python
class AppConfig(BaseModel, frozen=True):
    schema_version: int = 1
    app: AppRuntimeConfig
    llm: LLMConfig
    voice: VoiceConfig
    avatar: AvatarConfig
    tasks: TasksConfig
    ui: UIConfig
```

Module owners may only read their own sub-config; cross-reading is allowed but discouraged (use `EventBus.publish(ConfigUpdated(...))` for cross-cutting changes).

## 8. Mock skeletons

Every module ships a mock implementation that satisfies its Protocol. Mocks live at `packages/<module>/src/openmimicry/<module>/mocks.py` and are part of the public API.

These are the canonical mocks every other module may rely on:

```python
# openmimicry.llm.mocks
class MockLLMAdapter:
    """Yields a scripted sequence of LLMChunks. Pass `script=["Hello", " ", "world"]`."""

# openmimicry.voice.mocks
class MockSTTAdapter:
    """Programmable: call .push_transcript(...) to drive the async stream."""

class MockTTSAdapter:
    """Records every speak() call; stop() is honoured immediately."""

# openmimicry.avatar.mocks
class MockAvatarRuntimeAdapter:
    """Records every apply_directive() call into .directives_received."""

# openmimicry.tasks.mocks
class MockTaskRuntimeAdapter:
    """Submits return TaskHandle; updates() yields a scripted sequence."""
```

The exact constructor signatures and helper methods are defined in each module's brief (`docs/modules/Mx_*.md`).

## 9. Frontend wire protocol (subset)

The frontend never sees `RuntimeEvent` directly. It consumes a narrow projection over WebSocket. The schema below is the wire format; the backend in M6 owns the projection mapping.

```json
{ "type": "avatar.directive",  "directive": { /* AvatarDirective */ } }
{ "type": "transcript.preview","text": "...", "is_final": false }
{ "type": "bubble.text",       "text": "...", "complete": false }
{ "type": "task.card",         "update": { /* TaskUpdate */ } }
{ "type": "system.notice",     "level": "info|warn|error", "message": "..." }
```

The reverse direction (frontend → backend):

```json
{ "type": "user.text",  "text": "..." }
{ "type": "ptt.down" }
{ "type": "ptt.up" }
{ "type": "mode.toggle","key": "live_wake|agent_voice", "value": true }
```

These message names are part of the frozen contract. Adding new types is additive (minor version); removing or renaming requires a major bump.

## 10. Contract tests

Each protocol has a parametrised test in `tests/contract/`. Implementations register themselves via fixtures.

```text
tests/contract/
  test_llm.py             validates any LLMAdapter
  test_stt.py             validates any STTAdapter
  test_tts.py             validates any TTSAdapter
  test_speech_controller.py
  test_task_runtime.py    validates any TaskRuntimeAdapter
  test_avatar_runtime.py  validates any AvatarRuntimeAdapter
  conftest.py             registers all installed implementations
```

A module is "done" when its concrete adapter passes its contract test.

## 11. Change control

To change anything in this document:

1. Open a PR titled `contracts: <one-line summary>` and labelled `breaking` or `additive`.
2. Update `contracts.md` (this file), the Protocol code in `packages/openmimicry-core/src/openmimicry/core/contracts/`, the schemas, every mock that exposes the changed surface, and every contract test.
3. Bump `schema_version` if the change is breaking.
4. Add a `CHANGELOG.md` entry with a migration note.
5. Get approval from at least one other contributor (the "two-person rule" for the immutable surface).
6. Land the PR.
7. Notify any in-flight module agents that contracts moved.

The whole point of this document is that those seven steps are rare. Once Phase 0 lands, the goal is that this file does not change for the entire P1 wave.
