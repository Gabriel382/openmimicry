
"""Avatar pack loading helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from avatar.avatar_config import AvatarPackConfig, AvatarStateConfig


@dataclass(slots=True)
class LoadedAvatarPack:
    """Resolved avatar pack with filesystem paths."""

    root: Path
    config: AvatarPackConfig

    def get_state_config(self, state: str) -> AvatarStateConfig | None:
        """Return config for the requested state, if present."""
        return self.config.states.get(state)

    def get_fallback_state(self) -> str:
        """Return the configured fallback state."""
        return self.config.fallback_state

    def resolve_asset_path(self, state: str) -> Path | None:
        """Resolve the asset path for a state, falling back when needed."""
        state_config = self.get_state_config(state)
        if state_config is None:
            state_config = self.get_state_config(self.get_fallback_state())
            if state_config is None:
                return None
        asset_path = self.root / self.config.assets_dir / state_config.asset
        return asset_path if asset_path.exists() else None


def load_avatar_pack(pack_root: Path) -> LoadedAvatarPack:
    """Load a pack from its root folder."""
    config_path = pack_root / "avatar.toml"
    config = AvatarPackConfig.from_toml(config_path)
    return LoadedAvatarPack(root=pack_root, config=config)
