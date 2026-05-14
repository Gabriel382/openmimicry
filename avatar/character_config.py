
"""Character configuration models and TOML loading helpers for OpenMimicry 6.5."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import tomllib


VALID_PLAYBACK_MODES = {
    "noloop",
    "loopinfinity",
    "loopduringtime",
    "loopwhiletalk",
}


@dataclass(slots=True)
class BubbleConfig:
    """Bubble appearance and placement configuration."""

    image_path: str | None = None
    x_offset: int = 0
    y_offset: int = -180
    width: int = 300
    height: int = 100
    padding: int = 14
    auto_hide_ms: int = 0


@dataclass(slots=True)
class AnimationConfig:
    """Animation/state definition for a character."""

    path: str
    playback_mode: str = "loopinfinity"
    fps: int = 6
    duration_ms: int | None = None
    next_state: str = "idle"
    loop: bool | None = None
    text: str | None = None


@dataclass(slots=True)
class CharacterConfig:
    """Top-level character configuration."""

    name: str
    version: str = "0.1.0"
    default_state: str = "idle"
    fallback_state: str = "idle"
    root_scale: float = 1.0
    window_title: str = "OpenMimicry"
    bubble: BubbleConfig = field(default_factory=BubbleConfig)
    animations: dict[str, AnimationConfig] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CharacterConfig":
        """Build a config object from TOML data."""
        bubble_raw = data.get("bubble", {})
        bubble = BubbleConfig(
            image_path=bubble_raw.get("image_path"),
            x_offset=int(bubble_raw.get("x_offset", 0)),
            y_offset=int(bubble_raw.get("y_offset", -180)),
            width=int(bubble_raw.get("width", 300)),
            height=int(bubble_raw.get("height", 100)),
            padding=int(bubble_raw.get("padding", 14)),
            auto_hide_ms=int(bubble_raw.get("auto_hide_ms", 0)),
        )

        animations_raw = data.get("animations", {})
        animations: dict[str, AnimationConfig] = {}
        for state_name, state_data in animations_raw.items():
            playback_mode = state_data.get("playback_mode", "loopinfinity")
            if playback_mode not in VALID_PLAYBACK_MODES:
                raise ValueError(
                    f"Invalid playback_mode '{playback_mode}' for state '{state_name}'."
                )
            animations[state_name] = AnimationConfig(
                path=state_data["path"],
                playback_mode=playback_mode,
                fps=int(state_data.get("fps", 6)),
                duration_ms=(
                    None
                    if state_data.get("duration_ms") is None
                    else int(state_data["duration_ms"])
                ),
                next_state=state_data.get("next_state", data.get("default_state", "idle")),
                loop=state_data.get("loop"),
                text=state_data.get("text"),
            )

        return cls(
            name=data["name"],
            version=data.get("version", "0.1.0"),
            default_state=data.get("default_state", "idle"),
            fallback_state=data.get("fallback_state", "idle"),
            root_scale=float(data.get("root_scale", 1.0)),
            window_title=data.get("window_title", "OpenMimicry"),
            bubble=bubble,
            animations=animations,
        )

    @classmethod
    def from_toml(cls, path: Path) -> "CharacterConfig":
        """Load a character config from a TOML file."""
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        return cls.from_dict(data)
