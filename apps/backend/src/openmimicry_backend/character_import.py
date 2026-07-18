"""Secure character-pack discovery and ZIP installation."""

from __future__ import annotations

import io
import os
import re
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from openmimicry.core import CharacterPack

__all__ = ["CharacterImportError", "CharacterRegistry"]


_PACK_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
_MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
_MAX_EXPANDED_BYTES = 256 * 1024 * 1024
_MAX_ENTRIES = 2500


class CharacterImportError(ValueError):
    pass


class CharacterRegistry:
    def __init__(self, roots: list[str]) -> None:
        if not roots:
            raise CharacterImportError("avatar.pack_roots must contain a destination")
        self.roots = [Path(raw).expanduser().resolve() for raw in roots]

    @property
    def import_root(self) -> Path:
        root = self.roots[0]
        root.mkdir(parents=True, exist_ok=True)
        return root

    def list(self) -> list[dict[str, str]]:
        packs: dict[str, dict[str, str]] = {}
        for root in self.roots:
            if not root.is_dir():
                continue
            for manifest in sorted(root.glob("*/pack.yaml")):
                try:
                    raw = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
                    pack = CharacterPack.model_validate(raw)
                except Exception:
                    continue
                packs.setdefault(
                    pack.id,
                    {
                        "id": pack.id,
                        "name": pack.name,
                        "kind": pack.kind,
                        "path": str(manifest.parent),
                    },
                )
        return sorted(packs.values(), key=lambda item: item["name"].casefold())

    def resolve(self, pack_id: str) -> Path:
        for root in self.roots:
            candidate = root / pack_id
            if (candidate / "pack.yaml").is_file():
                return candidate
        raise CharacterImportError(f"character pack {pack_id!r} is not installed")

    def install_zip(self, archive: bytes, *, filename: str = "character.zip") -> dict[str, str]:
        if not filename.casefold().endswith(".zip"):
            raise CharacterImportError("character import requires a .zip file")
        if not archive:
            raise CharacterImportError("the uploaded ZIP is empty")
        if len(archive) > _MAX_ARCHIVE_BYTES:
            raise CharacterImportError("character ZIP exceeds the 64 MiB upload limit")

        root = self.import_root
        try:
            zipped = zipfile.ZipFile(io.BytesIO(archive))
        except zipfile.BadZipFile as exc:
            raise CharacterImportError("the uploaded file is not a valid ZIP") from exc

        with zipped:
            members = zipped.infolist()
            if len(members) > _MAX_ENTRIES:
                raise CharacterImportError("character ZIP contains too many files")
            if sum(member.file_size for member in members) > _MAX_EXPANDED_BYTES:
                raise CharacterImportError("expanded character ZIP exceeds 256 MiB")
            safe_names = [self._safe_member_name(member) for member in members]
            manifests = [name for name in safe_names if name.name == "pack.yaml"]
            if len(manifests) != 1:
                raise CharacterImportError(
                    "character ZIP must contain exactly one pack.yaml (at root or in one folder)"
                )
            manifest_parent = manifests[0].parent

            with tempfile.TemporaryDirectory(prefix=".openmimicry-import-", dir=root) as tmp:
                extraction = Path(tmp) / "contents"
                extraction.mkdir()
                for member, safe_name in zip(members, safe_names, strict=True):
                    target = extraction.joinpath(*safe_name.parts)
                    if member.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zipped.open(member) as source, target.open("wb") as destination:
                        while chunk := source.read(1024 * 1024):
                            destination.write(chunk)

                pack_root = extraction.joinpath(*manifest_parent.parts)
                pack = self._validate_pack(pack_root)
                destination = root / pack.id
                if destination.exists():
                    raise CharacterImportError(
                        f"character pack {pack.id!r} is already installed; choose a new id"
                    )
                os.replace(pack_root, destination)
                return {
                    "id": pack.id,
                    "name": pack.name,
                    "kind": pack.kind,
                    "path": str(destination),
                }

    @staticmethod
    def _safe_member_name(member: zipfile.ZipInfo) -> PurePosixPath:
        raw = member.filename.replace("\\", "/")
        path = PurePosixPath(raw)
        if (
            path.is_absolute()
            or not path.parts
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise CharacterImportError(f"unsafe ZIP path: {member.filename!r}")
        if path.parts[0].endswith(":"):
            raise CharacterImportError(f"unsafe ZIP drive path: {member.filename!r}")
        mode = member.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise CharacterImportError("symbolic links are not allowed in character ZIPs")
        return path

    @staticmethod
    def _validate_pack(root: Path) -> CharacterPack:
        manifest = root / "pack.yaml"
        try:
            raw: Any = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
            pack = CharacterPack.model_validate(raw)
        except Exception as exc:
            raise CharacterImportError(f"invalid pack.yaml: {exc}") from exc
        if not _PACK_ID.fullmatch(pack.id):
            raise CharacterImportError(
                "pack id must use 1-64 lowercase letters, numbers, '-' or '_'"
            )
        if not pack.emotions:
            raise CharacterImportError("pack.yaml must define at least one emotions state")
        for state_name, frames in pack.emotions.items():
            CharacterRegistry._validate_frames(root, state_name, "frames", frames.frames)
            if frames.speaking_frames is not None:
                CharacterRegistry._validate_frames(
                    root, state_name, "speaking_frames", frames.speaking_frames
                )
        if pack.preview:
            preview = (root / pack.preview).resolve()
            if not preview.is_file() or root.resolve() not in preview.parents:
                raise CharacterImportError(f"preview file is missing or unsafe: {pack.preview}")
        return pack

    @staticmethod
    def _validate_frames(root: Path, state_name: str, field: str, value: str | list[str]) -> None:
        values = value if isinstance(value, list) else [value]
        for raw in values:
            candidate = (root / raw).resolve()
            if root.resolve() not in candidate.parents:
                raise CharacterImportError(f"emotions.{state_name}.{field} escapes the pack")
            if isinstance(value, list):
                if not candidate.is_file() or candidate.suffix.casefold() not in _IMAGES:
                    raise CharacterImportError(
                        f"emotions.{state_name}.{field} image is missing: {raw}"
                    )
            elif not candidate.is_dir() or not any(
                item.is_file() and item.suffix.casefold() in _IMAGES for item in candidate.iterdir()
            ):
                raise CharacterImportError(
                    f"emotions.{state_name}.{field} folder has no images: {raw}"
                )
