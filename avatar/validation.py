
"""Avatar pack validation utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from avatar.avatar_pack import load_avatar_pack
from avatar.state_model import AvatarState


@dataclass(slots=True)
class AvatarValidationResult:
    """Validation output for an avatar pack."""

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_avatar_pack(pack_root: Path) -> AvatarValidationResult:
    """Validate an avatar pack structure and asset mapping."""
    errors: list[str] = []
    warnings: list[str] = []

    config_path = pack_root / "avatar.toml"
    if not config_path.exists():
        return AvatarValidationResult(
            ok=False,
            errors=[f"Missing config file: {config_path}"],
            warnings=[],
        )

    try:
        pack = load_avatar_pack(pack_root)
    except Exception as exc:
        return AvatarValidationResult(
            ok=False,
            errors=[f"Failed to load avatar pack: {exc}"],
            warnings=[],
        )

    if pack.config.default_state not in pack.config.states:
        errors.append(
            f"Default state '{pack.config.default_state}' is not defined in [states]."
        )

    if pack.config.fallback_state not in pack.config.states:
        errors.append(
            f"Fallback state '{pack.config.fallback_state}' is not defined in [states]."
        )

    for state_name, state_config in pack.config.states.items():
        asset_path = pack.root / pack.config.assets_dir / state_config.asset
        if not asset_path.exists():
            errors.append(f"Missing asset for state '{state_name}': {asset_path}")

    for required_state in AvatarState.values():
        if required_state not in pack.config.states:
            warnings.append(
                f"State '{required_state}' is missing. Runtime will use fallback state."
            )

    return AvatarValidationResult(
        ok=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
