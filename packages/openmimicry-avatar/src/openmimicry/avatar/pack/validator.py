"""``validate_pack(path) -> ValidationReport`` — non-raising check.

Used by:

* The CLI at ``scripts/validate_pack.py`` (exit 1 on any error).
* CI's ``make validate-packs`` step.
* Pack authors who want a structured "what's wrong" instead of a raised
  exception.

Errors block loading; warnings don't (and mirror the loader's fallback
rules in ``character_packs.md`` §6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from openmimicry.core.schemas import CharacterPack
from pydantic import ValidationError

from .loader import _FRAME_EXTENSIONS  # noqa: PLC2701 — same package

__all__ = ["ValidationReport", "validate_pack"]


@dataclass(frozen=True)
class ValidationReport:
    """Result of :func:`validate_pack`.

    ``ok`` is true iff ``errors`` is empty. Warnings do not gate loading.
    """

    path: str
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """One-line summary suitable for CLI output."""
        if self.ok and not self.warnings:
            return f"OK: {self.path}"
        if self.ok:
            return f"OK with {len(self.warnings)} warning(s): {self.path}"
        return f"FAIL with {len(self.errors)} error(s): {self.path}"


def validate_pack(pack_dir: Path | str) -> ValidationReport:
    """Validate a pack directory without raising."""
    root = Path(pack_dir).expanduser()
    errors: list[str] = []
    warnings: list[str] = []

    if not root.is_dir():
        return ValidationReport(
            path=str(root), ok=False, errors=[f"pack directory does not exist: {root}"]
        )

    manifest = root / "pack.yaml"
    if not manifest.is_file():
        return ValidationReport(
            path=str(root), ok=False, errors=[f"missing pack.yaml in {root}"]
        )

    try:
        raw = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return ValidationReport(
            path=str(root), ok=False, errors=[f"invalid YAML in {manifest}: {exc}"]
        )
    if not isinstance(raw, dict):
        return ValidationReport(
            path=str(root),
            ok=False,
            errors=[f"{manifest} top level must be a mapping"],
        )

    try:
        pack = CharacterPack.model_validate(raw)
    except ValidationError as exc:
        return ValidationReport(
            path=str(root),
            ok=False,
            errors=[f"{manifest} failed schema validation:\n{exc}"],
        )

    # Walk every emotion entry; flag missing folders/files and missing
    # speaking variants.
    for state, ef in pack.emotions.items():
        base_problem = _check(root, ef.frames, kind="frames", state=state)
        if base_problem:
            errors.append(base_problem)

        if ef.speaking_frames is None:
            warnings.append(
                f"emotions.{state}: missing speaking_frames; will fall back to base."
            )
        else:
            speaking_problem = _check(
                root, ef.speaking_frames, kind="speaking_frames", state=state
            )
            if speaking_problem:
                warnings.append(speaking_problem + " (will fall back to base)")

    return ValidationReport(
        path=str(root), ok=not errors, errors=errors, warnings=warnings
    )


def _check(root: Path, value: str | list[str], *, kind: str, state: str) -> str | None:
    """Return an error string if the referenced folder/list is broken; else None."""
    if isinstance(value, list):
        for item in value:
            p = (root / item).resolve() if not Path(item).is_absolute() else Path(item)
            if not p.is_file():
                return (
                    f"emotions.{state}.{kind}: missing file: {p}"
                )
        return None

    folder = (root / value).resolve() if not Path(value).is_absolute() else Path(value)
    if not folder.is_dir():
        return f"emotions.{state}.{kind}: folder does not exist: {folder}"
    has_any = any(
        p.is_file() and p.suffix.lower() in _FRAME_EXTENSIONS for p in folder.iterdir()
    )
    if not has_any:
        return f"emotions.{state}.{kind}: folder has no image files: {folder}"
    return None
