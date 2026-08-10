"""``wiring.py`` — the single assembly point for concrete adapter classes.

This is the **only** file in the repository (along with ``mocks.py`` files
and the test tree) that is allowed to ``import`` from
``openmimicry.{llm, voice, avatar, tasks}`` directly.
``scripts/check_imports.py`` has an explicit allowlist for this file.

Every other file in ``apps/backend/`` uses Protocols from
:mod:`openmimicry.core.contracts`.

Construction is pure dispatch from :class:`AppConfig` to concrete class —
no logic lives here. The returned :class:`Wiring` dataclass is the
container the rest of the backend reads through Protocol-typed
attributes.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

# Concrete imports — the rest of the backend may NOT do this.
from openmimicry.avatar import (
    AvatarDirector,
    AvatarOrchestrator,
    ExternalAvatarAdapter,
    Live3DAvatarAdapter,
    MockAvatarRuntimeAdapter,
    Sprite2DAvatarAdapter,
    ThreeJSAvatarAdapter,
    UnityAvatarAdapter,
)
from openmimicry.core import (
    AppConfig,
    AvatarRuntimeAdapter,
    EventBus,
    LLMAdapter,
    Runtime,
    SpeechController,
    STTAdapter,
    TaskRequest,
    TaskRuntimeAdapter,
    TTSAdapter,
)
from openmimicry.llm import (
    LiteLLMAdapter,
    LiteLLMSettings,
    LLMSwitchboard,
    MockLLMAdapter,
)
from openmimicry.memory import HindsightMemory, LocalSQLiteMemory, MemoryService, NullMemory
from openmimicry.memory.extractors import LLMExtractor
from openmimicry.tasks import (
    ClaudeCodeAdapter,
    ClaudeCodeSettings,
    JournaledTaskRuntime,
    LocalShellAdapter,
    MCPAgentAdapter,
    MockTaskRuntimeAdapter,
    PicoClawAdapter,
    PicoClawSettings,
    TaskJournal,
    TaskRouter,
    detect_task_intent,
)
from openmimicry.voice import (
    ChatterboxSettings,
    ChatterboxTTSAdapter,
    ElevenLabsSettings,
    ElevenLabsTTSAdapter,
    IsolatedFasterWhisperAdapter,
    IsolatedFasterWhisperSettings,
    IsolatedPiperSettings,
    IsolatedPiperTTSAdapter,
    MockSTTAdapter,
    MockTTSAdapter,
    RealtimeSTTAdapter,
    RealtimeTTSAdapter,
    SystemCommandTTSAdapter,
)
from openmimicry.voice import (
    SpeechController as ConcreteSpeechController,
)

__all__ = [
    "IntentClassifier",
    "Wiring",
    "WiringError",
    "build_runtime",
    "refresh_memory",
    "refresh_tts",
]


# The intent classifier signature, re-exposed so consumers in this
# package can type-check against ``Wiring.intent`` without importing
# anything from ``openmimicry.tasks``.
IntentClassifier = Callable[[str], TaskRequest | None]


_log = logging.getLogger(__name__)


class WiringError(RuntimeError):
    """Raised when ``AppConfig`` requests an adapter that isn't registered."""


# ---------------------------------------------------------------------------
# Wiring container
# ---------------------------------------------------------------------------


@dataclass
class Wiring:
    """The fully-assembled set of adapters + controllers."""

    runtime: Runtime
    bus: EventBus
    llm: LLMAdapter
    stt: STTAdapter
    tts: TTSAdapter
    speech: SpeechController
    director: Any
    avatar_runtime: AvatarRuntimeAdapter
    orchestrator: Any
    tasks: TaskRuntimeAdapter
    memory: MemoryService
    adapters_by_family: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    bridge: Any = None
    intent: IntentClassifier = detect_task_intent
    runtime_factories: Mapping[str, Callable[[], AvatarRuntimeAdapter]] = field(
        default_factory=dict
    )


# ---------------------------------------------------------------------------
# Build entrypoint
# ---------------------------------------------------------------------------


async def build_runtime(
    config: AppConfig,
    *,
    bus: EventBus | None = None,
    ws_bridge: Any | None = None,
    config_path: str | None = None,
) -> Wiring:
    """Assemble every concrete adapter from ``config`` and start the runtime."""
    bus = bus or EventBus()
    runtime = Runtime(config=config, bus=bus, config_path=config_path)
    await runtime.start()

    llm = _build_llm(config)
    memory = _build_memory(config, llm)
    stt = _build_stt(config)
    tts = _build_tts(config)
    speech: SpeechController = ConcreteSpeechController(
        stt=stt, tts=tts, bus=bus, config=config.voice
    )

    director = AvatarDirector(config=config.avatar)
    avatar_runtime = _build_avatar_runtime(config, ws_bridge=ws_bridge)
    orchestrator = AvatarOrchestrator(
        director=director,
        runtime=avatar_runtime,
        bus=bus,
        config=config.avatar,
    )

    task_router = _build_task_router(config)
    tasks = JournaledTaskRuntime(
        task_router,
        TaskJournal(config.tasks.database_path),
    )

    runtime_names = ("sprite2d", "threejs", "live3d", "unity", "external")
    runtime_factories: dict[str, Callable[[], AvatarRuntimeAdapter]] = {}
    for runtime_name in runtime_names:
        runtime_factories[runtime_name] = lambda selected=runtime_name: _build_named_avatar_runtime(
            selected, config, ws_bridge=ws_bridge
        )

    return Wiring(
        runtime=runtime,
        bus=bus,
        llm=llm,
        stt=stt,
        tts=tts,
        speech=speech,
        director=director,
        avatar_runtime=avatar_runtime,
        orchestrator=orchestrator,
        tasks=tasks,
        memory=memory,
        adapters_by_family={
            "llm": {llm.name: llm},
            "stt": {stt.name: stt},
            "tts": {tts.name: tts},
            "avatar": {avatar_runtime.name: avatar_runtime},
            "tasks": dict(_describe_task_adapters(task_router)),
        },
        bridge=ws_bridge,
        runtime_factories=runtime_factories,
    )


# ---------------------------------------------------------------------------
# Per-family dispatch
# ---------------------------------------------------------------------------


def _build_llm(config: AppConfig) -> LLMAdapter:
    if config.llm.backends:
        backends: dict[str, LLMAdapter] = {}
        models: dict[str, str] = {}
        for backend_name, backend in config.llm.backends.items():
            if backend.adapter == "mock":
                adapter: LLMAdapter = MockLLMAdapter()
            elif backend.adapter == "litellm":
                adapter = LiteLLMAdapter(
                    settings=LiteLLMSettings(
                        model=backend.model,
                        api_base=backend.api_base,
                        api_key_env=backend.api_key_env,
                        request_timeout_s=backend.request_timeout_s,
                        temperature=backend.temperature,
                        max_tokens=backend.max_tokens,
                        web_search_mode=backend.web_search_mode,
                    )
                )
            else:
                raise WiringError(
                    f"unknown llm.backends.{backend_name}.adapter: {backend.adapter!r}"
                )
            backends[backend_name] = adapter
            models[backend_name] = backend.model
        active = config.llm.active_backend or next(iter(backends))
        return LLMSwitchboard(backends=backends, models=models, active=active)

    name = config.llm.adapter
    if name == "mock":
        return MockLLMAdapter()
    if name == "litellm":
        settings = LiteLLMSettings(
            model=config.llm.model,
            api_base=config.llm.api_base,
            api_key_env=config.llm.api_key_env,
            request_timeout_s=config.llm.request_timeout_s,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
        )
        return LiteLLMAdapter(settings=settings)
    raise WiringError(f"unknown llm.adapter: {name!r}")


def _build_stt(config: AppConfig) -> STTAdapter:
    name = config.voice.stt.adapter
    if name == "mock":
        return MockSTTAdapter()
    if name == "isolated-faster-whisper":
        return IsolatedFasterWhisperAdapter(
            settings=IsolatedFasterWhisperSettings(
                device=config.voice.stt.device,
                compute_type=config.voice.stt.compute_type,
                beam_size=config.voice.stt.beam_size,
                speech_threshold=config.voice.stt.speech_threshold,
            )
        )
    if name == "realtimestt":
        from openmimicry.voice import RealtimeSTTSettings

        return RealtimeSTTAdapter(
            settings=RealtimeSTTSettings(
                model=config.voice.stt.model,
                realtime_model_type=config.voice.stt.realtime_model_type,
                use_main_model_for_realtime=config.voice.stt.use_main_model_for_realtime,
                language=config.voice.stt.language,
                sample_rate=config.voice.stt.sample_rate,
            )
        )
    raise WiringError(f"unknown voice.stt.adapter: {name!r}")


class _MemoryLLMCompletion:
    """Turn a selected streaming adapter into the memory extractor surface."""

    def __init__(self, adapter: LLMAdapter) -> None:
        self._adapter = adapter

    async def complete(self, prompt: str) -> str:
        from openmimicry.core import LLMMessage

        parts: list[str] = []
        async for chunk in self._adapter.generate(
            [
                LLMMessage(
                    role="system",
                    content="You extract durable user memories into strict JSON.",
                ),
                LLMMessage(role="user", content=prompt),
            ],
            stream=True,
            temperature=0.0,
        ):
            parts.append(chunk.delta)
        return "".join(parts)


def _build_memory(config: AppConfig, llm: LLMAdapter) -> MemoryService:
    memory = config.memory
    if not memory.enabled or memory.provider == "none":
        provider = NullMemory()
    elif memory.provider == "local":
        provider = LocalSQLiteMemory(
            memory.database_path,
            retention_days=memory.retention_days,
        )
    elif memory.provider == "hindsight":
        if memory.endpoint is None:
            raise WiringError("memory.endpoint is required for Hindsight")
        provider = HindsightMemory(base_url=memory.endpoint)
    else:  # pragma: no cover - Pydantic rejects unknown providers.
        raise WiringError(f"unknown memory.provider: {memory.provider!r}")

    llm_extractor = None
    if memory.enabled and memory.extraction_mode == "llm":
        selected: LLMAdapter = llm
        backend_getter = getattr(llm, "backend", None)
        backend_name = memory.llm_backend or config.llm.roles.memory_extract
        if callable(backend_getter):
            selected = cast(LLMAdapter, backend_getter(backend_name))
        llm_extractor = LLMExtractor(_MemoryLLMCompletion(selected))
    return MemoryService(
        provider=provider,
        retrieval_limit=memory.retrieval_limit,
        retrieval_deadline_ms=memory.retrieval_deadline_ms,
        extraction=memory.extraction_mode,
        llm_extractor=llm_extractor,
    )


async def refresh_memory(wiring: Wiring, candidate: AppConfig) -> MemoryService:
    """Build a replacement memory service, then retire the previous service."""

    replacement = _build_memory(candidate, wiring.llm)
    previous = wiring.memory
    wiring.memory = replacement
    await previous.close()
    return replacement


def _build_tts(config: AppConfig) -> TTSAdapter:
    name = config.voice.tts.adapter
    if name == "mock":
        return MockTTSAdapter()
    if name == "isolated-piper":
        return IsolatedPiperTTSAdapter(
            settings=IsolatedPiperSettings(data_dir=config.voice.tts.data_dir)
        )
    if name == "realtimetts":
        return RealtimeTTSAdapter()
    if name == "system-command":
        return SystemCommandTTSAdapter()
    if name == "elevenlabs":
        clone = config.voice.tts.clone
        if clone is None or clone.provider != "elevenlabs":
            raise WiringError("voice.tts.adapter=elevenlabs requires an elevenlabs clone config")
        secret_name = (
            config.voice.tts.secret.name
            if config.voice.tts.secret is not None and config.voice.tts.secret.source == "env"
            else "ELEVENLABS_API_KEY"
        )
        return ElevenLabsTTSAdapter(
            ElevenLabsSettings(
                voice_id=clone.voice_id,
                api_key_env=secret_name,
                endpoint=config.voice.tts.endpoint or "https://api.elevenlabs.io",
            )
        )
    if name == "chatterbox-local":
        clone = config.voice.tts.clone
        if clone is None or clone.provider != "chatterbox-local" or not clone.reference_path:
            raise WiringError(
                "voice.tts.adapter=chatterbox-local requires reference_path and consent_record"
            )
        return ChatterboxTTSAdapter(
            ChatterboxSettings(
                reference_path=clone.reference_path,
                consent_record=clone.consent_record,
                startup_timeout_s=config.voice.tts.readiness_timeout_s,
            )
        )
    raise WiringError(f"unknown voice.tts.adapter: {name!r}")


async def refresh_tts(wiring: Wiring, candidate: AppConfig) -> None:
    """Warm and swap only TTS while keeping the backend, STT, and tasks alive."""

    replacement = _build_tts(candidate)
    replacer = getattr(wiring.speech, "replace_tts", None)
    if not callable(replacer):
        raise WiringError("the active speech controller does not support hot TTS refresh")
    await cast(Callable[..., Awaitable[Any]], replacer)(
        replacement,
        config=candidate.voice,
    )
    wiring.tts = replacement
    families = wiring.adapters_by_family
    if isinstance(families, dict):
        families["tts"] = {replacement.name: replacement}


def _build_avatar_runtime(config: AppConfig, *, ws_bridge: Any | None) -> AvatarRuntimeAdapter:
    name = config.avatar.runtime
    if name == "mock":
        return MockAvatarRuntimeAdapter()
    if name == "sprite2d":
        return Sprite2DAvatarAdapter(ws_bridge=ws_bridge)
    if name == "threejs":
        runtime_cfg = {
            **config.avatar.runtimes.get("threejs", {}),
            "animation_speed": config.avatar.animation_speed,
        }
        return ThreeJSAvatarAdapter(ws_bridge=ws_bridge, runtime_cfg=runtime_cfg)
    if name == "live3d":
        runtime_cfg = config.avatar.runtimes.get("live3d", {})
        return Live3DAvatarAdapter(ws_bridge=ws_bridge, runtime_cfg=runtime_cfg)
    if name == "unity":
        runtime_cfg = config.avatar.runtimes.get("unity", {})
        return UnityAvatarAdapter(runtime_cfg=runtime_cfg)
    if name == "external":
        runtime_cfg = config.avatar.runtimes.get("external", {})
        return ExternalAvatarAdapter(runtime_cfg=runtime_cfg)
    raise WiringError(f"unknown avatar.runtime: {name!r}")


def _build_named_avatar_runtime(
    name: str,
    config: AppConfig,
    *,
    ws_bridge: Any | None,
) -> AvatarRuntimeAdapter:
    """Build a runtime by explicit name for ``POST /runtime/swap``."""

    if name == "sprite2d":
        return Sprite2DAvatarAdapter(ws_bridge=ws_bridge)
    if name == "threejs":
        return ThreeJSAvatarAdapter(
            ws_bridge=ws_bridge,
            runtime_cfg={
                **config.avatar.runtimes.get("threejs", {}),
                "animation_speed": config.avatar.animation_speed,
            },
        )
    if name == "live3d":
        return Live3DAvatarAdapter(
            ws_bridge=ws_bridge,
            runtime_cfg=config.avatar.runtimes.get("live3d", {}),
        )
    if name == "unity":
        return UnityAvatarAdapter(runtime_cfg=config.avatar.runtimes.get("unity", {}))
    if name == "external":
        return ExternalAvatarAdapter(runtime_cfg=config.avatar.runtimes.get("external", {}))
    raise WiringError(f"unknown avatar runtime: {name!r}")


def _build_task_router(config: AppConfig) -> TaskRouter:
    adapters: dict[str, Any] = {}
    for runtime_name, entry in config.tasks.runtimes.items():
        adapters[runtime_name] = _build_task_adapter(runtime_name, entry)
    if not adapters:
        adapters["mock"] = MockTaskRuntimeAdapter()
    default = config.tasks.default_runtime
    if default not in adapters:
        _log.warning(
            "tasks.default_runtime=%r not in registered adapters %r; using first instead",
            default,
            list(adapters),
        )
        default = next(iter(adapters))
    return TaskRouter(adapters=adapters, default_runtime=default)


def _build_task_adapter(name: str, entry: Any) -> Any:
    adapter_kind = entry.adapter
    options = entry.model_dump(exclude={"adapter"})
    if adapter_kind == "mock":
        return MockTaskRuntimeAdapter()
    if adapter_kind == "local_shell":
        return LocalShellAdapter()
    if adapter_kind == "claude_code":
        return ClaudeCodeAdapter(
            settings=ClaudeCodeSettings(
                cli=str(options.get("cli", "claude")),
                working_dir=_resolved_task_directory(str(options.get("working_dir", "."))),
                auth_mode=str(options.get("auth_mode", "subscription")),
                permission_mode=str(options.get("permission_mode", "acceptEdits")),
                model=(str(options["model"]) if options.get("model") else None),
                max_turns=(
                    int(options["max_turns"]) if options.get("max_turns") is not None else None
                ),
                diagnostic_timeout_s=float(options.get("diagnostic_timeout_s", 8.0)),
                extra_args=tuple(options.get("extra_args", ())),
            )
        )
    if adapter_kind == "picoclaw":
        return PicoClawAdapter(
            settings=PicoClawSettings(
                cli=str(options.get("cli", "picoclaw")),
                working_dir=_resolved_task_directory(str(options.get("working_dir", "."))),
            )
        )
    if adapter_kind == "mcp_agent":
        return MCPAgentAdapter()
    raise WiringError(f"unknown adapter kind for tasks.runtimes.{name!r}: {adapter_kind!r}")


def _resolved_task_directory(configured: str) -> str:
    """Resolve the repository root for an untouched first-run ``.`` value."""

    value = configured.strip() or "."
    if value not in {".", "./"}:
        return str(Path(value).expanduser().resolve())
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return str(candidate)
        if (candidate / "pyproject.toml").is_file() and (
            (candidate / "pnpm-workspace.yaml").is_file() or (candidate / "packages").is_dir()
        ):
            return str(candidate)
    return str(current)


def _describe_task_adapters(router: TaskRouter) -> Mapping[str, Any]:
    """Surface the router's underlying adapters for /health."""
    return getattr(router, "_adapters", {})
