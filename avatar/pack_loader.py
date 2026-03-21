
"""Avatar pack discovery and selection."""

from __future__ import annotations

from pathlib import Path

from avatar.avatar_pack import LoadedAvatarPack, load_avatar_pack


def discover_avatar_packs(packs_root: Path) -> list[str]:
    """Discover all avatar packs that contain an avatar.toml file."""
    results: list[str] = []
    if not packs_root.exists():
        return results
    for child in sorted(packs_root.iterdir()):
        if child.is_dir() and (child / "avatar.toml").exists():
            results.append(child.name)
    return results


def load_named_avatar_pack(packs_root: Path, pack_name: str) -> LoadedAvatarPack:
    """Load a named avatar pack from the packs directory."""
    pack_root = packs_root / pack_name
    if not pack_root.exists():
        raise FileNotFoundError(f"Avatar pack not found: {pack_name}")
    return load_avatar_pack(pack_root)
