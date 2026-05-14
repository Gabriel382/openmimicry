
"""Avatar pack config schema and loader."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import tomllib

from avatar.state_model import AvatarState


@dataclass(slots=True)
class AvatarStateConfig:
    """Configuration for a single avatar state."""

    asset: str
    duration_ms: int | None = None
    loop: bool = False
    speech_bubble_text: str | None = None


@dataclass(slots=True)
class AvatarPackConfig:
    """Top-level config for a 2D avatar pack."""

    name: str
    version: str = "0.1.0"
    default_state: str = AvatarState.IDLE.value
    fallback_state: str = AvatarState.IDLE.value
    assets_dir: str = "states"
    states: dict[str, AvatarStateConfig] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AvatarPackConfig":
        """Parse raw TOML data into a typed config object."""
        states_raw = data.get("states", {})
        states = {
            state_name: AvatarStateConfig(
                asset=state_data["asset"],
                duration_ms=state_data.get("duration_ms"),
                loop=bool(state_data.get("loop", False)),
                speech_bubble_text=state_data.get("speech_bubble_text"),
            )
            for state_name, state_data in states_raw.items()
        }
        return cls(
            name=data["name"],
            version=data.get("version", "0.1.0"),
            default_state=data.get("default_state", AvatarState.IDLE.value),
            fallback_state=data.get("fallback_state", AvatarState.IDLE.value),
            assets_dir=data.get("assets_dir", "states"),
            states=states,
        )

    @classmethod
    def from_toml(cls, path: Path) -> "AvatarPackConfig":
        """Load config from a TOML file."""
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        return cls.from_dict(data)
