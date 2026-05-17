"""``load_pack(path) -> CharacterPack`` — reads pack.yaml, validates, expands frames.

Per ``docs/character_packs.md`` §3 and §6. The loader:

1. Reads ``<path>/pack.yaml`` and parses it with PyYAML.
2. Validates the merged dict against the frozen :class:`CharacterPack`
   Pydantic schema from ``openmimicry.core.schemas.avatar``.
3. Walks every ``emotions[<state>]`` entry and resolves ``frames`` /
   ``speaking_frames``:
   - If a string, treated as a folder relative to the pack root and
     expanded to a sorted list of file paths.
   - If a list, kept as-is.
4. Applies fallback rules (§6):
   - Missing ``speaking_frames`` for a state -> emit a warning, fall back
     to the base ``frames`` (the validator surfaces this too).
   - Missing referenced folder/file -> raise :class:`PackLoadError`.

The returned :class:`CharacterPack` is frozen (Pydantic v2 default for our
schemas) so consumers can share it without defensive copies.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from openmimicry.core.schemas import CharacterPack, EmotionFrames
from pydantic import ValidationError

__all__ = [
    "PackLoadError",
    "load_pack",
    "resolve_frames",
]


_log = logging.getLogger(__name__)


# Image extensions considered "frames" when ``frames`` is a folder.
_FRAME_EXTENSIONS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
)


class PackLoadError(Exception):
    """Raised when a pack cannot be loaded."""


def load_pack(pack_dir: Path | str) -> CharacterPack:
    """Load and validate a character pack directory."""
    root = Path(pack_dir).expanduser()
    if not root.is_dir():
        raise PackLoadError(f"pack directory does not exist: {root}")

    manifest = root / "pack.yaml"
    if not manifest.is_file():
        raise PackLoadError(f"missing pack.yaml in {root}")

    try:
        raw = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise PackLoadError(f"invalid YAML in {manifest}: {exc}") from exc

    if not isinstance(raw, dict):
        raise PackLoadError(f"{manifest} top level must be a mapping")

    try:
        pack = CharacterPack.model_validate(raw)
    except ValidationError as exc:
        raise PackLoadError(
            f"{manifest} failed schema validation:\n{exc}"
        ) from exc

    # Walk emotions; resolve frames/speaking_frames; apply fallback rules.
    resolved: dict[str, EmotionFrames] = {}
    for state, ef in pack.emotions.items():
        base_paths = _resolve_one(root, ef.frames, kind="frames", state=state)
        if not base_paths:
            raise PackLoadError(
                f"{manifest}: emotions.{state}.frames resolved to zero files "
                f"(checked {root / ef.frames if isinstance(ef.frames, str) else ef.frames})"
            )

        if ef.speaking_frames is not None:
            speaking_paths = _resolve_one(
                root, ef.speaking_frames, kind="speaking_frames", state=state
            )
            if not speaking_paths:
                _log.warning(
                    "pack %s: emotions.%s.speaking_frames resolved to zero files; "
                    "falling back to base frames.",
                    pack.id,
                    state,
                )
                speaking_paths = list(base_paths)
        else:
            _log.warning(
                "pack %s: emotions.%s has no speaking_frames; falling back to base.",
                pack.id,
                state,
            )
            speaking_paths = list(base_paths)

        resolved[state] = ef.model_copy(
            update={"frames": list(base_paths), "speaking_frames": speaking_paths}
        )

    return pack.model_copy(update={"emotions": resolved})


def resolve_frames(pack_dir: Path | str, frames: str | list[str]) -> list[str]:
    """Public helper: resolve a ``frames`` value (folder or list) against a pack root.

    Used by both the loader and the validator so the rules stay in one place.
    """
    return _resolve_one(Path(pack_dir).expanduser(), frames, kind="frames", state="?")


def _resolve_one(
    root: Path, value: str | list[str], *, kind: str, state: str
) -> list[str]:
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            p = (root / item).resolve() if not Path(item).is_absolute() else Path(item)
            if not p.is_file():
                raise PackLoadError(
                    f"pack at {root}: emotions.{state}.{kind} references missing file: {p}"
                )
            out.append(str(p))
        return out

    # value is a folder path (string).
    folder = (root / value).resolve() if not Path(value).is_absolute() else Path(value)
    if not folder.is_dir():
        raise PackLoadError(
            f"pack at {root}: emotions.{state}.{kind} folder does not exist: {folder}"
        )
    files = sorted(
        p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in _FRAME_EXTENSIONS
    )
    return [str(p) for p in files]
