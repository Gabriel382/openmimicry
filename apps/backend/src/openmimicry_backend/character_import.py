"""Secure character-pack discovery and ZIP installation."""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import stat
import struct
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

    def export_zip(self, pack_id: str) -> bytes:
        """Return a portable archive for one validated installed pack."""

        root = self.resolve(pack_id)
        self._validate_pack(root)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for candidate in sorted(root.rglob("*")):
                if candidate.is_file():
                    archive.write(candidate, f"{pack_id}/{candidate.relative_to(root).as_posix()}")
        return buffer.getvalue()

    def delete(self, pack_id: str) -> None:
        """Delete only a private imported pack, never checked-in defaults."""

        root = self.resolve(pack_id).resolve()
        private_root = self.import_root.resolve()
        if root.parent != private_root:
            raise CharacterImportError("bundled/default characters cannot be removed")
        shutil.rmtree(root)

    def animation_clips(self, pack_id: str) -> list[str]:
        """Read embedded glTF/VRM animation names without loading model code."""

        return list(self.model_features(pack_id)["clips"])

    def model_features(self, pack_id: str) -> dict[str, Any]:
        """Inspect skeletal clips and VRM facial expressions in one model.

        VRM facial expressions are not glTF animation clips.  Reporting them
        separately prevents a rigged, expressive VRM from being described as
        having no animation support merely because it has no skeletal tracks.
        """

        root = self.resolve(pack_id)
        pack = self._validate_pack(root)
        asset = pack.metadata.get("asset") if pack.metadata else None
        path = str(asset.get("path")) if isinstance(asset, dict) and asset.get("path") else ""
        candidates = [root / path] if path else []
        candidates.extend((root / "character.vrm", root / "character.glb", root / "character.gltf"))
        model = next((item for item in candidates if item.is_file()), None)
        if model is None:
            return {"clips": [], "expressions": [], "expression_bindings": [], "vrm": None}
        try:
            if model.suffix.casefold() == ".gltf":
                document = json.loads(model.read_text(encoding="utf-8"))
            else:
                content = model.read_bytes()
                if len(content) < 20 or content[:4] != b"glTF":
                    return {
                        "clips": [],
                        "expressions": [],
                        "expression_bindings": [],
                        "vrm": None,
                    }
                offset = 12
                document = None
                while offset + 8 <= len(content):
                    length, chunk_type = struct.unpack_from("<II", content, offset)
                    offset += 8
                    chunk = content[offset : offset + length]
                    offset += length
                    if chunk_type == 0x4E4F534A:
                        document = json.loads(chunk.rstrip(b"\x00 \t\r\n").decode("utf-8"))
                        break
                if document is None:
                    return {
                        "clips": [],
                        "expressions": [],
                        "expression_bindings": [],
                        "vrm": None,
                    }
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, struct.error):
            return {"clips": [], "expressions": [], "expression_bindings": [], "vrm": None}
        animations = document.get("animations", []) if isinstance(document, dict) else []
        clips: list[str] = []
        for index, item in enumerate(animations):
            name = (
                str(item.get("name") or f"animation-{index + 1}") if isinstance(item, dict) else ""
            )
            if name and name not in clips:
                clips.append(name)

        expressions: list[str] = []
        bindings: list[dict[str, str]] = []
        vrm_version: str | None = None
        extensions = document.get("extensions", {}) if isinstance(document, dict) else {}
        if isinstance(extensions, dict) and isinstance(extensions.get("VRM"), dict):
            vrm_version = "0.x"
            blend_shapes = extensions["VRM"].get("blendShapeMaster", {})
            groups = (
                blend_shapes.get("blendShapeGroups", []) if isinstance(blend_shapes, dict) else []
            )
            preset_map = {
                "a": "aa",
                "i": "ih",
                "u": "ou",
                "e": "ee",
                "o": "oh",
                "joy": "happy",
                "sorrow": "sad",
                "fun": "relaxed",
                "lookup": "lookUp",
                "lookdown": "lookDown",
                "lookleft": "lookLeft",
                "lookright": "lookRight",
                "blink_l": "blinkLeft",
                "blink_r": "blinkRight",
            }
            if isinstance(groups, list):
                for group in groups:
                    if not isinstance(group, dict):
                        continue
                    source = str(group.get("name") or "").strip()
                    preset = str(group.get("presetName") or "unknown").strip()
                    runtime_name = preset_map.get(preset.casefold(), preset)
                    if not runtime_name or runtime_name.casefold() == "unknown":
                        runtime_name = source
                    if runtime_name and runtime_name not in expressions:
                        expressions.append(runtime_name)
                    if runtime_name:
                        bindings.append(
                            {
                                "source": source or runtime_name,
                                "preset": preset,
                                "runtime": runtime_name,
                            }
                        )
        vrm1 = extensions.get("VRMC_vrm") if isinstance(extensions, dict) else None
        if isinstance(vrm1, dict):
            vrm_version = str(vrm1.get("specVersion") or "1.x")
            expression_sets = vrm1.get("expressions", {})
            if isinstance(expression_sets, dict):
                for group_name in ("preset", "custom"):
                    values = expression_sets.get(group_name, {})
                    if not isinstance(values, dict):
                        continue
                    for name in values:
                        runtime_name = str(name).strip()
                        if runtime_name and runtime_name not in expressions:
                            expressions.append(runtime_name)
                        if runtime_name:
                            bindings.append(
                                {
                                    "source": runtime_name,
                                    "preset": group_name,
                                    "runtime": runtime_name,
                                }
                            )

        return {
            "clips": clips,
            "expressions": expressions,
            "expression_bindings": bindings,
            "vrm": vrm_version,
        }

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

    def install_vrm_archive(
        self,
        archive: bytes,
        *,
        pack_id: str,
        name: str,
        author: str,
        license_name: str,
        source_url: str = "",
        rotation_y: float = 180.0,
    ) -> dict[str, str]:
        """Install the sole VRM from a user-supplied custom archive.

        Only the VRM is copied into the private data directory; auxiliary
        PSD/FBX/Blend files are deliberately ignored. This makes custom
        archives usable without repackaging or adding copyrighted bytes to
        the OpenMimicry repository.
        """

        if not _PACK_ID.fullmatch(pack_id):
            raise CharacterImportError(
                "pack id must use 1-64 lowercase letters, numbers, '-' or '_'"
            )
        if not all(value.strip() for value in (name, author, license_name)):
            raise CharacterImportError("name, author, and original license terms are required")
        if not archive or len(archive) > _MAX_ARCHIVE_BYTES:
            raise CharacterImportError("VRM source ZIP must be 1 byte to 64 MiB")
        try:
            zipped = zipfile.ZipFile(io.BytesIO(archive))
        except zipfile.BadZipFile as exc:
            raise CharacterImportError("the uploaded file is not a valid ZIP") from exc
        with zipped:
            members = zipped.infolist()
            if len(members) > _MAX_ENTRIES:
                raise CharacterImportError("VRM source ZIP contains too many files")
            if sum(member.file_size for member in members) > _MAX_EXPANDED_BYTES:
                raise CharacterImportError("expanded VRM source ZIP exceeds 256 MiB")
            safe = [self._safe_member_name(member) for member in members]
            vrms = [
                (member, path)
                for member, path in zip(members, safe, strict=True)
                if not member.is_dir() and path.suffix.casefold() == ".vrm"
            ]
            if len(vrms) != 1:
                raise CharacterImportError(
                    "original character ZIP must contain exactly one .vrm model"
                )
            member, original_path = vrms[0]
            model = zipped.read(member)
        if len(model) < 12 or model[:4] != b"glTF":
            raise CharacterImportError("the .vrm entry is not a valid binary glTF container")

        destination = self.import_root / pack_id
        if destination.exists():
            raise CharacterImportError(
                f"character pack {pack_id!r} is already installed; choose a new id"
            )
        with tempfile.TemporaryDirectory(prefix=".openmimicry-vrm-", dir=self.import_root) as tmp:
            pack_root = Path(tmp) / pack_id
            pack_root.mkdir()
            (pack_root / "character.vrm").write_bytes(model)
            manifest = {
                "schema_version": 1,
                "id": pack_id,
                "name": name.strip(),
                "author": author.strip(),
                "license": license_name.strip(),
                "kind": "vrm",
                "default_state": "idle",
                "default_emotion": "neutral",
                "emotions": {},
                "metadata": {
                    "asset": {"kind": "vrm", "path": "character.vrm"},
                    "source_url": source_url.strip(),
                    "original_archive_entry": original_path.as_posix(),
                    "private_local_import": True,
                    "transform": {
                        "position": [0.0, 0.0, 0.0],
                        "rotation": [0.0, max(-360.0, min(360.0, float(rotation_y))), 0.0],
                        "scale": 1.0,
                        "auto_fit": True,
                        "target_height": 0.72,
                        "target_y": 1.3,
                    },
                    "redistribution_notice": (
                        "The model remains subject to the creator's original terms. "
                        "OpenMimicry does not grant redistribution rights."
                    ),
                },
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
        if pack.kind in {"vrm", "gltf", "threejs"}:
            metadata_asset = pack.metadata.get("asset") if pack.metadata else None
            candidates = [
                root / "character.vrm",
                root / "character.gltf",
                root / "character.glb",
            ]
            if isinstance(metadata_asset, dict) and metadata_asset.get("path"):
                candidates.insert(0, root / str(metadata_asset["path"]))
            resolved_root = root.resolve()
            if not any(
                item.resolve().is_file() and resolved_root in item.resolve().parents
                for item in candidates
            ):
                raise CharacterImportError(
                    "3D packs require character.vrm, character.gltf, character.glb, "
                    "or metadata.asset.path"
                )
        elif not pack.emotions:
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
