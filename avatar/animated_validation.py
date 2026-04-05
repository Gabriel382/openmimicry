
"""Validation helpers for animated 2D character packs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from avatar.character_pack import load_character_pack


@dataclass(slots=True)
class CharacterValidationResult:
    """Validation result for a character pack."""

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_character_pack(pack_root: Path) -> CharacterValidationResult:
    """Validate character config, animation folders, frames, and transitions."""
    errors: list[str] = []
    warnings: list[str] = []

    config_path = pack_root / "character.toml"
    if not config_path.exists():
        return CharacterValidationResult(
            ok=False,
            errors=[f"Missing character config: {config_path}"],
            warnings=[],
        )

    try:
        pack = load_character_pack(pack_root)
    except Exception as exc:
        return CharacterValidationResult(
            ok=False,
            errors=[f"Failed to load character pack: {exc}"],
            warnings=[],
        )

    if pack.config.default_state not in pack.config.animations:
        errors.append(f"Default state '{pack.config.default_state}' is not defined.")

    if pack.config.fallback_state not in pack.config.animations:
        errors.append(f"Fallback state '{pack.config.fallback_state}' is not defined.")

    for state_name, anim in pack.config.animations.items():
        anim_dir = pack.root / anim.path
        if not anim_dir.exists():
            errors.append(f"Missing animation directory for '{state_name}': {anim_dir}")
            continue

        frames = pack.frame_paths(state_name)
        if not frames:
            errors.append(f"No frames found for '{state_name}' in {anim_dir}")

        if anim.next_state not in pack.config.animations:
            warnings.append(
                f"State '{state_name}' points to unknown next_state '{anim.next_state}'."
            )

        if anim.playback_mode == "loopduringtime" and anim.duration_ms is None:
            warnings.append(
                f"State '{state_name}' uses loopduringtime but has no duration_ms."
            )

    bubble_path = pack.bubble_image_path()
    if pack.config.bubble.image_path and bubble_path is None:
        warnings.append("Bubble image path is configured but the file was not found.")

    return CharacterValidationResult(
        ok=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
