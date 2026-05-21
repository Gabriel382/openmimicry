"""AppConfig — the validated top-level configuration tree.

Source of truth: ``docs/contracts.md`` §7 and ``docs/configuration.md``.

Phase 0 ships the **shape** only. The loader (env overlay, profile merge,
hot-reload, ``schema_version`` migrations) lives in
``openmimicry.core.config`` and is delivered by M0.

All sub-configs are frozen Pydantic v2 models. Module owners read their own
sub-config off the parsed ``AppConfig``; cross-reading is permitted but the
preferred way to react to runtime changes is to subscribe to
``ConfigUpdated`` on the EventBus.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .avatar import Emotion, State
from .vision import VisionConfig

__all__ = [
    "SCHEMA_VERSION",
    "AppConfig",
    "AppRuntimeConfig",
    "AvatarConfig",
    "HotkeysConfig",
    "LLMConfig",
    "LLMFallbackConfig",
    "LLMRetryConfig",
    "OverlayConfig",
    "PanelConfig",
    "STTConfigSection",
    "STTWakeConfig",
    "TTSConfigSection",
    "TaskRuntimeConfigEntry",
    "TasksConfig",
    "TrayConfig",
    "UIConfig",
    "VisionConfig",
    "VoiceConfig",
    "VoiceModesConfig",
]


SCHEMA_VERSION: int = 1
"""The schema version this package understands. Bump on breaking changes."""


# ---------------------------------------------------------------------------
# app.*  — process-wide runtime settings
# ---------------------------------------------------------------------------


class AppRuntimeConfig(BaseModel):
    """Top-level ``app:`` section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "text"] = "json"
    data_dir: str = "~/.openmimicry"
    telemetry: bool = False
    config_watch: bool = False


# ---------------------------------------------------------------------------
# llm.*
# ---------------------------------------------------------------------------


class LLMRetryConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    attempts: int = 2
    backoff_s: float = 1.5


class LLMFallbackConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    adapter: str = "litellm"
    model: str = "ollama/llama3.1"


class LLMConfig(BaseModel):
    """``llm:`` section.

    The adapter name is a string (not a literal) so third-party adapters can be
    registered without touching this schema.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    adapter: str = "litellm"
    model: str = "openrouter/anthropic/claude-3.5-sonnet"
    temperature: float = 0.7
    max_tokens: int | None = None
    api_base: str | None = None
    api_key_env: str | None = "OPENROUTER_API_KEY"
    request_timeout_s: int = 60
    retry: LLMRetryConfig = Field(default_factory=LLMRetryConfig)
    fallback: LLMFallbackConfig | None = Field(default_factory=LLMFallbackConfig)


# ---------------------------------------------------------------------------
# voice.*
# ---------------------------------------------------------------------------


class STTWakeConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    names: list[str] = ["Mimi", "Hey Mimi"]
    sensitivity: float = 0.6


class STTConfigSection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    adapter: str = "realtimestt"
    language: str = "en"
    vad: Literal["silero", "webrtc", "none"] = "silero"
    sample_rate: int = 16000
    wake: STTWakeConfig = Field(default_factory=STTWakeConfig)


class TTSConfigSection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    adapter: str = "realtimetts"
    engine: str = "coqui"
    voice: str = "en_female_1"
    rate: float = 1.0
    interruptible: bool = True


class VoiceModesConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text_always_on: bool = True
    push_to_talk_hotkey: str = "Ctrl+Space"
    live_wake: bool = True
    agent_voice: bool = True
    barge_in_grace_ms: int = 600


class VoiceConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    stt: STTConfigSection = Field(default_factory=STTConfigSection)
    tts: TTSConfigSection = Field(default_factory=TTSConfigSection)
    modes: VoiceModesConfig = Field(default_factory=VoiceModesConfig)


# ---------------------------------------------------------------------------
# avatar.*
# ---------------------------------------------------------------------------


class AvatarConfig(BaseModel):
    """``avatar:`` section.

    Per-runtime configuration (``runtimes.sprite2d``, ``runtimes.threejs``, …)
    is intentionally loose — each modality owns its own keys. The avatar module
    re-validates the sub-tree against its own schema when it loads.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    runtime: str = "sprite2d"
    pack: str = "octomimic"
    pack_roots: list[str] = ["./characters", "~/.openmimicry/characters"]
    default_state: State = "idle"
    default_emotion: Emotion = "neutral"
    transition_ms: int = 120
    celebration_ms: int = 1200
    error_ms: int = 1000
    runtimes: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# tasks.*
# ---------------------------------------------------------------------------


class TaskRuntimeConfigEntry(BaseModel):
    """One entry under ``tasks.runtimes.<name>``.

    Only ``adapter`` is universal; everything else depends on the runtime
    (``servers`` for ``mcp_agent``, ``cli`` for ``claude_code`` …) and is kept
    in ``extra``.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    adapter: str


class TasksConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    default_runtime: str = "mcp_agent"
    runtimes: dict[str, TaskRuntimeConfigEntry] = {}


# ---------------------------------------------------------------------------
# ui.*
# ---------------------------------------------------------------------------


class OverlayConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    width: int = 360
    height: int = 360
    fit_to_character: bool = False
    interactive_padding_px: int = 40
    click_through_default: bool = True
    always_on_top: bool = True
    save_position: bool = True


class PanelConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    width: int = 480
    height: int = 720
    open_on_startup: bool = False


class TrayConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True


class HotkeysConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    toggle_interact: str = "Ctrl+Shift+M"
    show_panel: str = "Ctrl+Shift+O"


class UIConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    overlay: OverlayConfig = Field(default_factory=OverlayConfig)
    panel: PanelConfig = Field(default_factory=PanelConfig)
    tray: TrayConfig = Field(default_factory=TrayConfig)
    hotkeys: HotkeysConfig = Field(default_factory=HotkeysConfig)


# ---------------------------------------------------------------------------
# AppConfig (top level)
# ---------------------------------------------------------------------------


class AppConfig(BaseModel):
    """The validated top-level configuration tree."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = SCHEMA_VERSION
    app: AppRuntimeConfig = Field(default_factory=AppRuntimeConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    avatar: AvatarConfig = Field(default_factory=AvatarConfig)
    tasks: TasksConfig = Field(default_factory=TasksConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    # Optional and **off by default**. Absent or ``enabled=False``
    # means no camera ever opens.
    vision: VisionConfig | None = None
