"""Utilities for loading a simple image-based avatar pack."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
import json

from .state_model import AvatarState


@dataclass(slots=True)
class AvatarPack:
    """Loaded avatar pack metadata and asset paths."""

    name: str
    root: Path
    width: int
    height: int
    bubble_enabled: bool
    states: Dict[AvatarState, Path]

    @classmethod
    def load(cls, root: str | Path) -> "AvatarPack":
        """Load an avatar pack from a folder.

        Expected structure:
            pack/
              manifest.json
              states/
                idle.png
                listening.png
                thinking.png
                speaking.png
                happy.png
                error.png
        """
        root = Path(root)
        manifest_path = root / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Missing avatar manifest: {manifest_path}")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        width = int(manifest.get("width", 320))
        height = int(manifest.get("height", 320))
        bubble_enabled = bool(manifest.get("bubble_enabled", True))

        state_dir = root / "states"
        states: Dict[AvatarState, Path] = {}
        for state in AvatarState:
            state_path = state_dir / f"{state.value}.png"
            if state_path.exists():
                states[state] = state_path

        if AvatarState.IDLE not in states:
            raise ValueError("Avatar pack must include states/idle.png")

        # Fill missing states with the idle image to keep packs easy to build.
        for state in AvatarState:
            states.setdefault(state, states[AvatarState.IDLE])

        return cls(
            name=str(manifest.get("name", root.name)),
            root=root,
            width=width,
            height=height,
            bubble_enabled=bubble_enabled,
            states=states,
        )

    def asset_for(self, state: AvatarState) -> Path:
        """Return the image path for a given state."""
        return self.states.get(state, self.states[AvatarState.IDLE])
