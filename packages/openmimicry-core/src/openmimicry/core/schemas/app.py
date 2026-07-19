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

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .avatar import Emotion, State
from .vision import VisionConfig

__all__ = [
    "SCHEMA_VERSION",
    "AppConfig",
    "AppRuntimeConfig",
    "AvatarConfig",
    "DistributionConfig",
    "HotkeysConfig",
    "InteractionConfig",
    "LLMBackendConfig",
    "LLMConfig",
    "LLMFallbackConfig",
    "LLMRetryConfig",
    "LLMRoleAssignments",
    "MemoryConfig",
    "OverlayConfig",
    "PanelConfig",
    "ResponsePresentationConfig",
    "STTConfigSection",
    "STTWakeConfig",
    "SecretReference",
    "TTSCloneConfig",
    "TTSConfigSection",
    "TaskRuntimeConfigEntry",
    "TasksConfig",
    "TrayConfig",
    "UIConfig",
    "VisionConfig",
    "VoiceConfig",
    "VoiceModesConfig",
]


SCHEMA_VERSION: int = 2
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


class SecretReference(BaseModel):
    """A credential locator. Secret values never enter :class:`AppConfig`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: Literal["env", "session", "keyring"] = "env"
    name: str = Field(min_length=1, max_length=128)


class LLMBackendConfig(BaseModel):
    """One named, dashboard-selectable LLM backend."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    adapter: str = "litellm"
    provider: str = "openai-compatible"
    model: str
    temperature: float = 0.7
    max_tokens: int | None = None
    api_base: str | None = None
    api_key_env: str | None = None
    secret: SecretReference | None = None
    catalog_url: str | None = None
    enabled: bool = True
    request_timeout_s: int = 60


class LLMRoleAssignments(BaseModel):
    """Independent backend selection for each LLM-consuming role."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    conversation: str | None = None
    memory_extract: str | None = None
    memory_embed: str | None = None


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
    # If ``backends`` is populated, the active named backend replaces the
    # legacy single-adapter fields above.  Keeping both shapes makes v1.4 an
    # additive configuration change for existing collaborators.
    active_backend: str | None = None
    backends: dict[str, LLMBackendConfig] = {}
    roles: LLMRoleAssignments = Field(default_factory=LLMRoleAssignments)
    history_turns: int = Field(default=4, ge=0, le=10)

    @model_validator(mode="after")
    def active_backend_is_configured(self) -> LLMConfig:
        if (
            self.backends
            and self.active_backend is not None
            and self.active_backend not in self.backends
        ):
            raise ValueError(
                f"llm.active_backend {self.active_backend!r} is not present in llm.backends"
            )
        configured_roles = {
            role
            for role in (
                self.roles.conversation,
                self.roles.memory_extract,
                self.roles.memory_embed,
            )
            if role is not None
        }
        missing = configured_roles.difference(self.backends)
        if self.backends and missing:
            raise ValueError(f"llm.roles references unknown backends: {sorted(missing)}")
        return self


# ---------------------------------------------------------------------------
# voice.*
# ---------------------------------------------------------------------------


class STTWakeConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    names: list[str] = ["Mimi", "Hey Mimi"]
    aliases: list[str] = ["Me me"]
    sensitivity: float = 0.6


class STTConfigSection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    adapter: str = "isolated-faster-whisper"
    language: str = "en"
    model: str = "medium.en"
    realtime_model_type: str = "medium.en"
    use_main_model_for_realtime: bool = True
    device: Literal["auto", "cpu", "cuda"] = "auto"
    compute_type: str = "auto"
    beam_size: int = Field(default=5, ge=1, le=10)
    speech_threshold: float = Field(default=0.015, gt=0.0, le=1.0)
    vad: Literal["silero", "webrtc", "none"] = "silero"
    sample_rate: int = 16000
    # Require this much silence before finalising a phrase. RealtimeSTT's
    # upstream 0.2 s default is too eager for ordinary conversational pauses.
    post_speech_silence_duration: float = Field(default=1.0, ge=0.2, le=3.0)
    wake: STTWakeConfig = Field(default_factory=STTWakeConfig)


class TTSCloneConfig(BaseModel):
    """Reference to a separately prepared, explicitly consented cloned voice."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: Literal["chatterbox-local", "elevenlabs"]
    voice_id: str = Field(min_length=1, max_length=128)
    consent_record: str = Field(min_length=1, max_length=256)
    reference_path: str | None = None
    store_reference_locally: bool = True


class TTSConfigSection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    adapter: str = "isolated-piper"
    engine: str = "piper"
    voice: str = "en_US-lessac-medium"
    data_dir: str = "~/.openmimicry/voices"
    rate: float = 1.0
    interruptible: bool = True
    # Local voice-cloning models may need a cold-start model load before the
    # first audio frame.  Keep the bounded wait configurable per profile while
    # retaining a short default for ordinary local/system voices.
    readiness_timeout_s: float = Field(default=30.0, ge=1.0, le=180.0)
    endpoint: str | None = None
    secret: SecretReference | None = None
    clone: TTSCloneConfig | None = None


class VoiceModesConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text_always_on: bool = True
    push_to_talk_hotkey: str = "Ctrl+Space"
    # ``continuous_listening`` is ordinary VAD-driven dictation: the user
    # starts speaking without first saying a wake name. ``live_wake`` remains
    # as a backwards-compatible, advanced wake-word mode.
    continuous_listening: bool = False
    live_wake: bool = False
    agent_voice: bool = True
    # Speaker output commonly re-enters laptop microphones. Keep automatic
    # VAD barge-in opt-in; PTT always interrupts TTS explicitly and safely.
    barge_in_enabled: bool = False
    barge_in_grace_ms: int = 600


class VoiceConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    stt: STTConfigSection = Field(default_factory=STTConfigSection)
    tts: TTSConfigSection = Field(default_factory=TTSConfigSection)
    modes: VoiceModesConfig = Field(default_factory=VoiceModesConfig)


# ---------------------------------------------------------------------------
# interaction.*, memory.*, distribution.*
# ---------------------------------------------------------------------------


class ResponsePresentationConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: Literal["parallel", "voice_ready", "text_only", "voice_only"] = "parallel"
    dismiss_policy: Literal["after_both"] = "after_both"
    minimum_ms: int = Field(default=2500, ge=250, le=60000)
    base_ms: int = Field(default=1500, ge=0, le=60000)
    ms_per_character: int = Field(default=55, ge=0, le=1000)
    maximum_ms: int = Field(default=30000, ge=1000, le=300000)
    allow_accessibility_captions: bool = True

    @model_validator(mode="after")
    def timer_bounds_are_ordered(self) -> ResponsePresentationConfig:
        if self.maximum_ms < self.minimum_ms:
            raise ValueError("interaction.response_presentation.maximum_ms must be >= minimum_ms")
        return self


class InteractionConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    response_presentation: ResponsePresentationConfig = Field(
        default_factory=ResponsePresentationConfig
    )
    show_rejected_wake_transcripts: bool = True
    restore_geometry: bool = True


class MemoryConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    provider: Literal["none", "local", "hindsight"] = "none"
    database_path: str = "~/.openmimicry/memory/memory.sqlite3"
    endpoint: str | None = None
    retrieval_limit: int = Field(default=6, ge=0, le=50)
    retrieval_deadline_ms: int = Field(default=150, ge=25, le=5000)
    retention_days: int | None = Field(default=365, ge=1, le=36500)
    extraction_mode: Literal["deterministic", "llm"] = "deterministic"
    llm_backend: str | None = None
    store_raw_audio: Literal[False] = False

    @model_validator(mode="after")
    def enabled_provider_is_explicit(self) -> MemoryConfig:
        if self.enabled and self.provider == "none":
            raise ValueError("memory.enabled=true requires provider local or hindsight")
        if self.provider == "hindsight" and self.enabled and not self.endpoint:
            raise ValueError("memory.provider=hindsight requires memory.endpoint")
        return self


class DistributionConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    profile: Literal["core", "local", "cloud", "commercial", "community"] = "commercial"
    reject_licenses: list[str] = [
        "GPL",
        "AGPL",
        "non-commercial",
        "CC-BY-NC",
        "CC BY-NC",
        "research-only",
        "unknown",
    ]


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
    interaction: InteractionConfig = Field(default_factory=InteractionConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    avatar: AvatarConfig = Field(default_factory=AvatarConfig)
    tasks: TasksConfig = Field(default_factory=TasksConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    distribution: DistributionConfig = Field(default_factory=DistributionConfig)
    # Optional and **off by default**. Absent or ``enabled=False``
    # means no camera ever opens.
    vision: VisionConfig | None = None
