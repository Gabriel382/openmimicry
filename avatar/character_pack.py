
"""Character pack loading and frame discovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from avatar.character_config import CharacterConfig


@dataclass(slots=True)
class CharacterPack:
    """Loaded character pack with resolved frame paths."""

    root: Path
    config: CharacterConfig

    def animation_dir(self, state: str) -> Path:
        """Return the directory for a state."""
        state_config = self.config.animations.get(state)
        if state_config is None:
            state_config = self.config.animations[self.config.fallback_state]
        return self.root / state_config.path

    def frame_paths(self, state: str) -> list[Path]:
        """Return sorted frame paths for a state, with fallback behavior."""
        state_config = self.config.animations.get(state)
        if state_config is None:
            state = self.config.fallback_state
            state_config = self.config.animations.get(state)

        if state_config is None:
            return []

        anim_dir = self.root / state_config.path
        if not anim_dir.exists():
            fallback_config = self.config.animations.get(self.config.fallback_state)
            if fallback_config is None:
                return []
            anim_dir = self.root / fallback_config.path
            if not anim_dir.exists():
                return []

        frames = [
            path
            for path in sorted(anim_dir.iterdir())
            if path.suffix.lower() in {".png", ".webp"}
        ]
        return frames

    def bubble_image_path(self) -> Path | None:
        """Resolve optional bubble image path."""
        if not self.config.bubble.image_path:
            return None
        path = self.root / self.config.bubble.image_path
        return path if path.exists() else None


def load_character_pack(root: Path) -> CharacterPack:
    """Load a character pack from its root directory."""
    config = CharacterConfig.from_toml(root / "character.toml")
    return CharacterPack(root=root, config=config)
