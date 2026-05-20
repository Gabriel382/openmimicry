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
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

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

# Concrete imports — the rest of the backend may NOT do this.
from openmimicry.avatar import (
    AvatarDirector,
    AvatarOrchestrator,
    MockAvatarRuntimeAdapter,
    Sprite2DAvatarAdapter,
    ThreeJSAvatarAdapter,
)
from openmimicry.llm import LiteLLMAdapter, LiteLLMSettings, MockLLMAdapter
from openmimicry.tasks import (
    ClaudeCodeAdapter,
    LocalShellAdapter,
    MCPAgentAdapter,
    MockTaskRuntimeAdapter,
    TaskRouter,
    detect_task_intent,
)
from openmimicry.voice import (
    MockSTTAdapter,
    MockTTSAdapter,
    RealtimeSTTAdapter,
    RealtimeTTSAdapter,
    SpeechController as ConcreteSpeechController,
)

__all__ = ["IntentClassifier", "Wiring", "WiringError", "build_runtime"]


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
    adapters_by_family: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    bridge: Any = None
    intent: IntentClassifier = detect_task_intent


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
        tasks=task_router,
        adapters_by_family={
            "llm": {llm.name: llm},
            "stt": {stt.name: stt},
            "tts": {tts.name: tts},
            "avatar": {avatar_runtime.name: avatar_runtime},
            "tasks": dict(_describe_task_adapters(task_router)),
        },
        bridge=ws_bridge,
    )


# ---------------------------------------------------------------------------
# Per-family dispatch
# ---------------------------------------------------------------------------


def _build_llm(config: AppConfig) -> LLMAdapter:
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
    if name == "realtimestt":
        return RealtimeSTTAdapter()
    raise WiringError(f"unknown voice.stt.adapter: {name!r}")


def _build_tts(config: AppConfig) -> TTSAdapter:
    name = config.voice.tts.adapter
    if name == "mock":
        return MockTTSAdapter()
    if name == "realtimetts":
        return RealtimeTTSAdapter()
    raise WiringError(f"unknown voice.tts.adapter: {name!r}")


def _build_avatar_runtime(
    config: AppConfig, *, ws_bridge: Any | None
) -> AvatarRuntimeAdapter:
    name = config.avatar.runtime
    if name == "mock":
        return MockAvatarRuntimeAdapter()
    if name == "sprite2d":
        return Sprite2DAvatarAdapter(ws_bridge=ws_bridge)
    if name == "threejs":
        runtime_cfg = config.avatar.runtimes.get("threejs", {})
        return ThreeJSAvatarAdapter(ws_bridge=ws_bridge, runtime_cfg=runtime_cfg)
    raise WiringError(f"unknown avatar.runtime: {name!r}")


def _build_task_router(config: AppConfig) -> TaskRouter:
    adapters: dict[str, Any] = {}
    for runtime_name, entry in config.tasks.runtimes.items():
        adapters[runtime_name] = _build_task_adapter(runtime_name, entry.adapter)
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


def _build_task_adapter(name: str, adapter_kind: str) -> Any:
    if adapter_kind == "mock":
        return MockTaskRuntimeAdapter()
    if adapter_kind == "local_shell":
        return LocalShellAdapter()
    if adapter_kind == "claude_code":
        return ClaudeCodeAdapter()
    if adapter_kind == "mcp_agent":
        return MCPAgentAdapter()
    raise WiringError(
        f"unknown adapter kind for tasks.runtimes.{name!r}: {adapter_kind!r}"
    )


def _describe_task_adapters(router: TaskRouter) -> Mapping[str, Any]:
    """Surface the router's underlying adapters for /health."""
    return getattr(router, "_adapters", {})
