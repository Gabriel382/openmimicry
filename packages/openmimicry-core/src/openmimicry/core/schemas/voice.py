"""Voice schemas — frozen Pydantic models.

Source of truth: ``docs/contracts.md`` §4.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "STTConfig",
    "TTSChunkBoundary",
    "TTSConfig",
    "Transcript",
    "WakeEvent",
]


class STTConfig(BaseModel):
    """Runtime configuration handed to ``STTAdapter.start``."""

    model_config = ConfigDict(frozen=True)

    language: str = "en"
    # The low-level contract keeps a lightweight legacy default. The Windows
    # application profile explicitly selects the stronger medium.en model.
    model: str = "small.en"
    realtime_model_type: str = "small.en"
    use_main_model_for_realtime: bool = True
    mode: Literal["wake", "dictation", "push_to_talk", "continuous"] = "dictation"
    wake_names: list[str] = []
    prompt_terms: list[str] = []
    sample_rate: int = 16000
    vad: Literal["silero", "webrtc", "none"] = "silero"
    post_speech_silence_duration: float = Field(default=1.0, ge=0.2, le=3.0)


class TTSConfig(BaseModel):
    """Runtime configuration handed to ``TTSAdapter.speak``."""

    model_config = ConfigDict(frozen=True)

    engine: str = "coqui"
    voice: str = "en_female_1"
    rate: float = 1.0
    interruptible: bool = True


class Transcript(BaseModel):
    """A transcript fragment emitted by ``STTAdapter.transcripts``."""

    model_config = ConfigDict(frozen=True)

    text: str
    is_final: bool
    confidence: float | None = None
    segments: list[dict] = []


class WakeEvent(BaseModel):
    """Emitted by ``WakeController`` when a wake-name is detected."""

    model_config = ConfigDict(frozen=True)

    name: str
    confidence: float | None = None


class TTSChunkBoundary(BaseModel):
    """A heartbeat surfaced by ``TTSAdapter`` mid-playback.

    Used by the avatar director to drive mouth-flap / speaking-variant cycles.
    """

    model_config = ConfigDict(frozen=True)

    bytes_played: int
    timestamp_ms: int
