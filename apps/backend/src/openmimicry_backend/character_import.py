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
_MAX_CREATOR_IMAGE_BYTES = 8 * 1024 * 1024
_SPRITE_STATES = ("idle", "listening", "thinking", "speaking", "happy", "error")


class CharacterImportError(ValueError):
    pass


class CharacterRegistry:
    def __init__(
        self,
        roots: list[str],
        *,
        reject_licenses: list[str] | None = None,
    ) -> None:
        if not roots:
            raise CharacterImportError("avatar.pack_roots must contain a destination")
        self.roots = [Path(raw).expanduser().resolve() for raw in roots]
        self.reject_licenses = [item.casefold() for item in (reject_licenses or [])]

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
                        "license": pack.license or "unknown",
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
                self._validate_license(pack)
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
                    "license": pack.license or "unknown",
                    "path": str(destination),
                }

    def create_sprite_pack(
        self,
        *,
        pack_id: str,
        name: str,
        author: str,
        license_name: str,
        sprites: dict[str, bytes],
        fps: int = 6,
    ) -> dict[str, str]:
        """Create a conservative static/single-frame Sprite2D pack atomically."""

        if not _PACK_ID.fullmatch(pack_id):
            raise CharacterImportError(
                "pack id must use 1-64 lowercase letters, numbers, '-' or '_'"
            )
        if not name.strip() or len(name) > 128:
            raise CharacterImportError("character name must contain 1-128 characters")
        if not author.strip() or len(author) > 128:
            raise CharacterImportError("author/owner must contain 1-128 characters")
        if not license_name.strip() or len(license_name) > 128:
            raise CharacterImportError("license or ownership statement is required")
        if "idle" not in sprites:
            raise CharacterImportError("an idle PNG/WebP/JPEG/GIF sprite is required")
        if set(sprites).difference(_SPRITE_STATES):
            raise CharacterImportError("sprites contains an unsupported lifecycle state")
        for state, image in sprites.items():
            if not image or len(image) > _MAX_CREATOR_IMAGE_BYTES:
                raise CharacterImportError(f"{state} sprite exceeds the 8 MiB limit")
            _detect_image_extension(image)

        destination = self.import_root / pack_id
        if destination.exists():
            raise CharacterImportError(
                f"character pack {pack_id!r} is already installed; choose a new id"
            )
        with tempfile.TemporaryDirectory(
            prefix=".openmimicry-create-", dir=self.import_root
        ) as tmp:
            pack_root = Path(tmp) / pack_id
            pack_root.mkdir()
            emotions: dict[str, dict[str, object]] = {}
            idle = sprites["idle"]
            speaking = sprites.get("speaking", idle)
            for state in _SPRITE_STATES:
                state_image = sprites.get(state, idle)
                state_dir = pack_root / state
                speaking_dir = pack_root / f"{state}_speaking"
                state_dir.mkdir()
                speaking_dir.mkdir()
                state_ext = _detect_image_extension(state_image)
                speaking_ext = _detect_image_extension(speaking)
                (state_dir / f"000{state_ext}").write_bytes(state_image)
                (speaking_dir / f"000{speaking_ext}").write_bytes(speaking)
                emotions[state] = {
                    "frames": state,
                    "speaking_frames": f"{state}_speaking",
                    "fps": fps,
                    "loop": state not in {"happy", "error"},
                }
            manifest = {
                "schema_version": 1,
                "id": pack_id,
                "name": name.strip(),
                "author": author.strip(),
                "license": license_name.strip(),
                "kind": "sprite2d",
                "preview": f"idle/000{_detect_image_extension(idle)}",
                "default_state": "idle",
                "default_emotion": "neutral",
                "transition_ms": 120,
                "emotions": emotions,
                "metadata": {"created_by": "OpenMimicry v1.6 character creator"},
            }
            (pack_root / "pack.yaml").write_text(
                yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            pack = self._validate_pack(pack_root)
            self._validate_license(pack)
            os.replace(pack_root, destination)
        return {
            "id": pack.id,
            "name": pack.name,
            "kind": pack.kind,
            "license": pack.license or "unknown",
            "path": str(destination),
        }

    def _validate_license(self, pack: CharacterPack) -> None:
        if not self.reject_licenses:
            return
        license_name = (pack.license or "unknown").casefold()
        if any(rejected in license_name for rejected in self.reject_licenses):
            raise CharacterImportError(
                f"character license {pack.license or 'unknown'!r} is rejected by the active distribution profile"
            )

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


def _detect_image_extension(content: bytes) -> str:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    raise CharacterImportError("sprite is not a supported PNG, WebP, JPEG, or GIF image")
