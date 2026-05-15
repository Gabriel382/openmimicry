# Adapters

This document specifies the five adapter contracts that sit between OpenMimicry's runtime and the outside world: LLMs, speech-to-text, text-to-speech, external task runtimes, and **avatar runtimes**. The runtime depends on the contracts; concrete libraries depend on nothing in OpenMimicry beyond `openmimicry-core.schemas`.

All contracts are async by default and surfaced as `typing.Protocol` so adapters can be duck-typed and unit tests can mock them trivially.

The full discussion of the six avatar modalities (Sprite2D, Advanced 2D, Three.js / VRM / glTF, Live 3D, Unity, External), their directive schema mapping, and install profiles lives in [`avatar_modalities.md`](./avatar_modalities.md). This document gives the contract itself, alongside the other four.

## 1. LLMAdapter

```python
# packages/openmimicry-llm/src/openmimicry/llm/base.py
from typing import AsyncIterator, Protocol, Sequence
from openmimicry.core.schemas.llm import LLMChunk, LLMMessage, ToolSpec

class LLMAdapter(Protocol):
    name: str
    """Stable id used in config (e.g. 'litellm', 'mock')."""

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        stream: bool = True,
        tools: Sequence[ToolSpec] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Yield LLMChunks. If stream=False, yields exactly one terminal chunk."""

    async def healthcheck(self) -> bool: ...

    async def close(self) -> None: ...
```

Reference implementation: `LiteLLMAdapter` in `packages/openmimicry-llm/src/openmimicry/llm/litellm_adapter.py`. It wraps `litellm.acompletion(..., stream=True)` and translates the OpenAI-style chunks into `LLMChunk`.

Error model:

- Provider/network errors raise `LLMTransportError` (retryable).
- Auth/permission errors raise `LLMAuthError` (not retryable).
- Tool-call malformed responses raise `LLMToolCallError`.
- The router catches these to decide on fallback (e.g. fall back to Ollama if the cloud provider fails).

Routing: `openmimicry.llm.router.LLMRouter` wraps a primary adapter and an optional fallback. It is itself an `LLMAdapter`, so consumers only ever see one interface.

## 2. STTAdapter

```python
# packages/openmimicry-voice/src/openmimicry/voice/stt/base.py
from typing import AsyncIterator, Protocol
from openmimicry.core.schemas.voice import Transcript, STTConfig

class STTAdapter(Protocol):
    name: str

    async def start(self, config: STTConfig) -> None:
        """Open the mic and begin streaming. Idempotent if already started."""

    async def stop(self) -> None: ...

    @property
    def transcripts(self) -> AsyncIterator[Transcript]:
        """Hot stream of partial + final transcripts since start()."""

    async def healthcheck(self) -> bool: ...
```

Reference: `RealtimeSTTAdapter` wraps `RealtimeSTT.AudioToTextRecorder`. It bridges RealtimeSTT's callbacks to the async stream by pushing into an `asyncio.Queue`.

VAD and wake-word are configured via `STTConfig`. The adapter is responsible for emitting `is_final=True` transcripts; partial transcripts are first-class but tagged `is_final=False`.

## 3. TTSAdapter

```python
# packages/openmimicry-voice/src/openmimicry/voice/tts/base.py
from typing import AsyncIterable, Callable, Protocol
from openmimicry.core.schemas.voice import TTSConfig, TTSChunkBoundary

OnChunk = Callable[[TTSChunkBoundary], None]

class TTSAdapter(Protocol):
    name: str

    async def speak(
        self,
        text_or_stream: str | AsyncIterable[str],
        *,
        config: TTSConfig,
        on_chunk: OnChunk | None = None,
    ) -> None:
        """Play `text` (or a token stream). Returns when playback finishes
        OR when stop() is called. Cooperative cancellation: implementations
        must check a cancel flag between chunks."""

    async def stop(self) -> None:
        """Cancel any in-progress speak() promptly. Idempotent."""

    @property
    def is_speaking(self) -> bool: ...

    async def healthcheck(self) -> bool: ...
```

Reference: `RealtimeTTSAdapter` wraps `RealtimeTTS.TextToAudioStream` with a configurable engine (Coqui, Piper, Azure, etc.). It feeds the engine the iterable of tokens directly when a stream is passed, which is what enables low-latency speak-as-you-think.

`on_chunk` fires on audio chunk boundaries so the avatar can emit a `speaking=true` heartbeat without polling.

## 4. SpeechController

The controller is the only module that touches both STT and TTS. It exists to make barge-in and PTT safe.

```python
# packages/openmimicry-voice/src/openmimicry/voice/controllers/speech.py
class SpeechController:
    def __init__(self, stt: STTAdapter, tts: TTSAdapter, bus: EventBus, cfg: VoiceConfig): ...

    async def start(self) -> None: ...
    async def stop(self) -> None: ...

    # Text/voice output
    async def say(self, text_or_stream: str | AsyncIterable[str]) -> None:
        """Cancels any currently-speaking utterance, then speaks the new one."""

    async def interrupt(self) -> None: ...

    # Voice input
    async def ptt_down(self) -> None: ...
    async def ptt_up(self) -> None: ...

    async def enable_live_listening(self, *, wake_names: list[str] | None) -> None: ...
    async def disable_live_listening(self) -> None: ...
```

The controller publishes `TTSStarted`, `TTSChunkSpoken`, `TTSFinished`, `TTSInterrupted`, `UserSpeechStarted`, `UserSpeechFinal`, and `WakeDetected` on the bus.

## 5. WakeController

```python
class WakeController:
    def __init__(self, stt: STTAdapter, bus: EventBus, cfg: WakeConfig): ...
    async def enable(self) -> None: ...
    async def disable(self) -> None: ...
```

The wake controller is a small wrapper that puts the STT into a low-cost wake-listening mode and emits `WakeDetected` events; the speech controller flips the STT to full transcription mode in response.

## 6. TaskRuntimeAdapter

```python
# packages/openmimicry-tasks/src/openmimicry/tasks/base.py
from typing import AsyncIterator, Protocol
from openmimicry.core.schemas.tasks import (
    TaskRequest, TaskHandle, TaskStatus, TaskUpdate, TaskResult,
)

class TaskRuntimeAdapter(Protocol):
    name: str
    capabilities: set[str]  # e.g. {"shell", "code_edit", "browse", "mcp"}

    async def submit(self, req: TaskRequest) -> TaskHandle: ...
    async def status(self, handle: TaskHandle) -> TaskStatus: ...
    async def cancel(self, handle: TaskHandle) -> None: ...
    def updates(self, handle: TaskHandle) -> AsyncIterator[TaskUpdate]: ...
    async def result(self, handle: TaskHandle) -> TaskResult: ...

    async def healthcheck(self) -> bool: ...
```

Routing: `TaskRouter` picks an adapter based on `req.capabilities_required`, user preference (`tasks.default_runtime`), and adapter health. The avatar/runtime sees only the router.

Shipped reference adapters:

- `mcp_agent_adapter` — uses `mcp-agent` to expose MCP-server-backed agents.
- `claude_code_adapter` — spawns and supervises the `claude` CLI, parses streaming output.
- `openclaw_adapter`, `picoclaw_adapter` — talk to those runtimes over their respective wire protocols.
- `local_shell_adapter` — runs allow-listed shell commands locally (defense-in-depth: allowlist + working-directory pin + read/write scopes from config).
- `mock_adapter` — for tests and demos.

## 7. AvatarRuntimeAdapter

The avatar runtime is the fifth and final outward-facing adapter. It is the contract between OpenMimicry's normalized directive stream and *whatever* renders the avatar — a 2D sprite renderer, a Three.js VRM viewer, a Unity scene over WebSocket, or a third-party engine.

```python
# packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/base.py
from typing import Protocol
from openmimicry.core.schemas.avatar import AvatarDirective

class AvatarRuntimeAdapter(Protocol):
    name: str
    capabilities: set[str]  # e.g. {"2d", "speaking_variants"} or {"3d", "gestures", "gaze"}

    async def load_character(self, character_id: str, config: dict) -> None: ...
    async def apply_directive(self, directive: AvatarDirective) -> None: ...
    async def set_text(self, text: str) -> None: ...
    async def start_speaking(self, text: str | None = None) -> None: ...
    async def stop_speaking(self) -> None: ...
    async def set_visibility(self, visible: bool) -> None: ...
    async def healthcheck(self) -> bool: ...
    async def shutdown(self) -> None: ...
```

Two implementation rules every adapter must follow:

- Accept any well-formed `AvatarDirective` without raising; ignore fields you do not support (Sprite2D ignores `gesture`, `gaze`, `intensity` — that's by design).
- Be cancellation-safe; a new `apply_directive` may arrive before the previous transition finishes, and the implementation collapses to the latest intent.

Shipped reference adapters:

```text
Sprite2DAvatarAdapter        sprite2d                ships with [basic]
Advanced2DAvatarAdapter      live2d|spine|rive|...   ships with [advanced2d]
ThreeJSAvatarAdapter         threejs                 ships with [threejs]
VRMAvatarAdapter             vrm                     ships with [threejs]
Live3DAvatarAdapter          live3d                  ships with [threejs] + [live3d]
UnityAvatarAdapter           unity                   ships with [unity]
ExternalAvatarAdapter        external                ships with core (transport-only)
MockAvatarAdapter            mock                    ships with core (tests)
```

For the per-modality directive field mapping and a worked Live 3D example, see [`avatar_modalities.md`](./avatar_modalities.md) §3.

## 8. AvatarDirector and AvatarOrchestrator

The director and orchestrator are not adapters to the outside world, but they are the glue that wires events to whichever avatar runtime is loaded.

```python
# packages/openmimicry-avatar/src/openmimicry/avatar/director.py
class AvatarDirector:
    def __init__(self, pack: CharacterPack, cfg: AvatarConfig): ...
    def on_event(self, event: RuntimeEvent) -> AvatarDirective | None:
        """Return a new directive if state changed, else None."""

# packages/openmimicry-avatar/src/openmimicry/avatar/orchestrator.py
class AvatarOrchestrator:
    def __init__(self, director, runtime: AvatarRuntimeAdapter, bus, cfg): ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def swap_runtime(self, new_runtime: AvatarRuntimeAdapter) -> None: ...
```

The backend wires `AvatarOrchestrator` to the bus. The orchestrator asks the director for a directive on each relevant event and hands it to the loaded `AvatarRuntimeAdapter`. `swap_runtime` lets the user change modality (e.g. Sprite2D → Three.js) without restarting the backend.

## 9. Lifecycle and dependency injection

The backend assembles adapters in `apps/backend/wiring.py`:

```python
def build_runtime(cfg: AppConfig, bus: EventBus) -> Runtime:
    llm = build_llm_adapter(cfg.llm)                 # picks LiteLLMAdapter
    stt = build_stt_adapter(cfg.voice.stt)           # picks RealtimeSTTAdapter
    tts = build_tts_adapter(cfg.voice.tts)           # picks RealtimeTTSAdapter
    tasks = build_task_router(cfg.tasks)             # composes task adapters
    speech = SpeechController(stt, tts, bus, cfg.voice)
    director = AvatarDirector(load_pack(cfg.avatar.pack), cfg.avatar)
    avatar_runtime = build_avatar_runtime(cfg.avatar)  # Sprite2D / ThreeJS / Unity / ...
    orchestrator = AvatarOrchestrator(director, avatar_runtime, bus, cfg.avatar)
    return Runtime(bus, llm, speech, tasks, orchestrator, cfg)
```

Each `build_*_adapter` is the single point that imports a concrete library. Everywhere else, the runtime only ever sees the protocols above.

## 10. Versioning the contracts

The five protocols in this document are the public API of OpenMimicry's plugin surface. They follow SemVer with the package version:

- Adding optional kwargs or new optional methods is a minor bump.
- Removing methods, renaming, or changing semantics is a major bump.
- Both directions ship with a migration note in `CHANGELOG.md`.

Until v1.0, contract churn is expected; that is exactly what the `0.x` line is for.
