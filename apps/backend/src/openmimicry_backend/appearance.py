"""Public, non-secret desktop appearance configuration.

The main :class:`AppConfig` owns runtime behaviour. ``config/theme.yml`` is
deliberately separate: collaborators can tune window geometry, colours and
speech-bubble timing without touching provider or security settings.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

__all__ = ["AppearanceConfig", "load_appearance"]


class OverlayWindowAppearance(BaseModel):
    model_config = ConfigDict(extra="ignore")

    width: int = Field(default=360, ge=240, le=1600)
    height: int = Field(default=420, ge=240, le=1600)
    transparent: bool = True
    frameless: bool = True
    always_on_top: bool = True
    movable: bool = True


class ControlsWindowAppearance(BaseModel):
    model_config = ConfigDict(extra="ignore")

    width: int = Field(default=360, ge=240, le=1600)
    height: int = Field(default=92, ge=44, le=320)
    always_on_top: bool = True


class PanelWindowAppearance(BaseModel):
    model_config = ConfigDict(extra="ignore")

    width: int = Field(default=480, ge=360, le=1800)
    height: int = Field(default=720, ge=480, le=1800)


class WindowAppearance(BaseModel):
    model_config = ConfigDict(extra="ignore")

    overlay: OverlayWindowAppearance = Field(default_factory=OverlayWindowAppearance)
    controls: ControlsWindowAppearance = Field(default_factory=ControlsWindowAppearance)
    panel: PanelWindowAppearance = Field(default_factory=PanelWindowAppearance)


class ThemeAppearance(BaseModel):
    model_config = ConfigDict(extra="ignore")

    font_family: str = "Inter, Arial, sans-serif"
    bubble_bg: str = "rgba(20, 20, 22, 0.88)"
    bubble_text: str = "#f4f4f6"
    controls_bg: str = "rgba(18, 22, 30, 0.82)"
    controls_border: str = "rgba(255, 255, 255, 0.14)"
    input_bg: str = "rgba(255, 255, 255, 0.10)"
    input_border: str = "rgba(255, 255, 255, 0.18)"
    accent: str = "#ff8a3d"
    panel_bg: str = "#16161a"
    panel_text: str = "#dddddd"


class LayoutAppearance(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bubble_max_width: int = Field(default=330, ge=160, le=1200)
    avatar_width: int = Field(default=330, ge=120, le=1400)
    avatar_scale: float = Field(default=1.0, ge=0.25, le=3.0)
    controls_gap: int = Field(default=6, ge=0, le=80)


class BubbleBehaviour(BaseModel):
    model_config = ConfigDict(extra="ignore")

    base_ms: int = Field(default=2500, ge=0, le=60000)
    ms_per_character: int = Field(default=55, ge=0, le=1000)
    max_ms: int = Field(default=30000, ge=1000, le=300000)


class ControlsBehaviour(BaseModel):
    model_config = ConfigDict(extra="ignore")

    show: bool = True
    show_drag_handle: bool = True
    show_text_input: bool = True
    drag_label: str = "Drag OpenMimicry"


class BehaviourAppearance(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bubble: BubbleBehaviour = Field(default_factory=BubbleBehaviour)
    controls: ControlsBehaviour = Field(default_factory=ControlsBehaviour)


class AppearanceConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: int = 1
    windows: WindowAppearance = Field(default_factory=WindowAppearance)
    theme: ThemeAppearance = Field(default_factory=ThemeAppearance)
    layout: LayoutAppearance = Field(default_factory=LayoutAppearance)
    behaviour: BehaviourAppearance = Field(default_factory=BehaviourAppearance)


def load_appearance(path: str | os.PathLike[str] | None = None) -> AppearanceConfig:
    """Load ``config/theme.yml`` or return validated defaults.

    ``OPENMIMICRY_APPEARANCE_PATH`` supports per-user files outside the repo.
    Invalid files fail closed to defaults so a colour typo cannot prevent the
    backend from starting.
    """

    raw_path = path or os.environ.get("OPENMIMICRY_APPEARANCE_PATH") or "config/theme.yml"
    candidate = Path(raw_path).expanduser()
    if not candidate.is_file():
        return AppearanceConfig()
    try:
        loaded = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
        return AppearanceConfig.model_validate(loaded)
    except Exception:
        return AppearanceConfig()
