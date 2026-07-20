"""Private named Voice Profile storage with bounded import/export."""

from __future__ import annotations

import io
import os
import re
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

__all__ = ["VoiceProfileError", "VoiceProfileStore", "audio_extension"]


_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_MAX_AUDIO = 20 * 1024 * 1024
_MAX_ARCHIVE = 24 * 1024 * 1024


class VoiceProfileError(ValueError):
    pass


def audio_extension(content: bytes, filename: str) -> str:
    lowered = filename.casefold()
    if content.startswith(b"RIFF") and content[8:12] == b"WAVE":
        return ".wav"
    if content.startswith(b"ID3") or content.startswith((b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
        return ".mp3"
    if lowered.endswith((".wav", ".mp3")):
        raise VoiceProfileError("audio signature does not match WAV/MP3")
    raise VoiceProfileError("reference must be a WAV or MP3 file")


class VoiceProfileStore:
    def __init__(self, data_dir: str | Path) -> None:
        self.root = Path(data_dir).expanduser().resolve() / "voices" / "profiles"

    def list(self) -> list[dict[str, Any]]:
        profiles: list[dict[str, Any]] = []
        if not self.root.is_dir():
            return profiles
        for manifest in sorted(self.root.glob("*/profile.yaml")):
            try:
                profile = self._read_manifest(manifest.parent)
            except VoiceProfileError:
                continue
            profiles.append(self.public(profile, manifest.parent))
        return sorted(profiles, key=lambda item: str(item["name"]).casefold())

    def resolve(self, profile_id: str) -> tuple[dict[str, Any], Path]:
        self._validate_id(profile_id)
        directory = (self.root / profile_id).resolve()
        if directory.parent != self.root or not directory.is_dir():
            raise VoiceProfileError(f"voice profile {profile_id!r} is not installed")
        return self._read_manifest(directory), directory

    def match_active(
        self,
        *,
        provider: str,
        voice_id: str,
        reference_path: str | None,
    ) -> str | None:
        """Recover the named profile represented by the loaded TTS config."""

        configured_reference = (
            Path(reference_path).expanduser().resolve() if reference_path else None
        )
        if not self.root.is_dir():
            return None
        for manifest in sorted(self.root.glob("*/profile.yaml")):
            directory = manifest.parent
            try:
                profile = self._read_manifest(directory)
            except VoiceProfileError:
                continue
            if profile.get("provider") != provider or profile.get("voice_id") != voice_id:
                continue
            reference = profile.get("reference")
            if provider == "chatterbox-local":
                if not isinstance(reference, str) or configured_reference is None:
                    continue
                if (directory / reference).resolve() != configured_reference:
                    continue
            return str(profile["id"])
        return None

    def create_reference(
        self,
        *,
        profile_id: str,
        name: str,
        consent_record: str,
        filename: str,
        audio: bytes,
    ) -> dict[str, Any]:
        self._validate_new(profile_id, name, consent_record)
        if not audio or len(audio) > _MAX_AUDIO:
            raise VoiceProfileError("reference audio must be 1 byte to 20 MiB")
        extension = audio_extension(audio, filename)
        profile = {
            "schema_version": 1,
            "id": profile_id,
            "name": name.strip(),
            "provider": "chatterbox-local",
            "engine": "chatterbox-turbo",
            "voice_id": "local-reference",
            "consent_record": consent_record.strip(),
            "reference": f"reference{extension}",
            "language": "en",
            "rate": 1.0,
        }
        directory = self._write_new(profile_id, profile, {profile["reference"]: audio})
        return self.public(profile, directory)

    def create_remote(
        self, *, profile_id: str, name: str, voice_id: str, consent_record: str
    ) -> dict[str, Any]:
        self._validate_new(profile_id, name, consent_record)
        if not voice_id.strip() or len(voice_id) > 128:
            raise VoiceProfileError("ElevenLabs voice id must contain 1-128 characters")
        profile = {
            "schema_version": 1,
            "id": profile_id,
            "name": name.strip(),
            "provider": "elevenlabs",
            "engine": "eleven_multilingual_v2",
            "voice_id": voice_id.strip(),
            "consent_record": consent_record.strip(),
            "reference": None,
            "language": "multilingual",
            "rate": 1.0,
        }
        directory = self._write_new(profile_id, profile, {})
        return self.public(profile, directory)

    def export(self, profile_id: str, *, include_reference: bool) -> bytes:
        profile, directory = self.resolve(profile_id)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            exported = dict(profile)
            reference = profile.get("reference")
            if not include_reference:
                exported["reference"] = None
            archive.writestr(
                "profile.yaml", yaml.safe_dump(exported, sort_keys=False, allow_unicode=True)
            )
            if include_reference and isinstance(reference, str):
                archive.write(directory / reference, f"voice/{reference}")
        return buffer.getvalue()

    def import_zip(self, content: bytes, *, confirm_reference: bool) -> dict[str, Any]:
        if not content or len(content) > _MAX_ARCHIVE:
            raise VoiceProfileError("voice profile ZIP must be 1 byte to 24 MiB")
        try:
            archive = zipfile.ZipFile(io.BytesIO(content))
        except zipfile.BadZipFile as exc:
            raise VoiceProfileError("voice profile is not a valid ZIP") from exc
        with archive:
            members = archive.infolist()
            if len(members) > 8 or sum(item.file_size for item in members) > _MAX_ARCHIVE:
                raise VoiceProfileError("voice profile ZIP exceeds safe limits")
            names = {self._safe_name(item): item for item in members if not item.is_dir()}
            manifest_member = names.get(PurePosixPath("profile.yaml"))
            if manifest_member is None:
                raise VoiceProfileError("voice profile ZIP is missing profile.yaml")
            profile = self._validate_profile(
                yaml.safe_load(archive.read(manifest_member).decode("utf-8")) or {}
            )
            reference = profile.get("reference")
            files: dict[str, bytes] = {}
            if isinstance(reference, str):
                if not confirm_reference:
                    raise VoiceProfileError("confirm biometric reference import explicitly")
                member = names.get(PurePosixPath("voice") / reference)
                if member is None:
                    raise VoiceProfileError("voice reference declared by profile is missing")
                audio = archive.read(member)
                audio_extension(audio, reference)
                files[reference] = audio
            directory = self._write_new(str(profile["id"]), profile, files)
            return self.public(profile, directory)

    @staticmethod
    def public(profile: dict[str, Any], directory: Path) -> dict[str, Any]:
        return {
            "id": profile["id"],
            "name": profile["name"],
            "provider": profile["provider"],
            "engine": profile["engine"],
            "voice_id": profile["voice_id"],
            "reference_configured": bool(profile.get("reference")),
            "consent_configured": bool(profile.get("consent_record")),
            "path": str(directory),
        }

    def _write_new(self, profile_id: str, profile: dict[str, Any], files: dict[str, bytes]) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        destination = self.root / profile_id
        if destination.exists():
            raise VoiceProfileError(f"voice profile {profile_id!r} already exists")
        with tempfile.TemporaryDirectory(prefix=".voice-profile-", dir=self.root) as temporary:
            staging = Path(temporary) / profile_id
            staging.mkdir()
            (staging / "profile.yaml").write_text(
                yaml.safe_dump(profile, sort_keys=False, allow_unicode=True), encoding="utf-8"
            )
            for name, content in files.items():
                target = staging / name
                descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "wb") as output:
                    output.write(content)
            os.replace(staging, destination)
        return destination

    def _read_manifest(self, directory: Path) -> dict[str, Any]:
        try:
            value = yaml.safe_load((directory / "profile.yaml").read_text(encoding="utf-8")) or {}
        except Exception as exc:
            raise VoiceProfileError(f"invalid voice profile: {exc}") from exc
        return self._validate_profile(value)

    def _validate_profile(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise VoiceProfileError("voice profile schema_version must be 1")
        profile_id = str(value.get("id") or "")
        self._validate_id(profile_id)
        name = str(value.get("name") or "").strip()
        provider = value.get("provider")
        if not name or len(name) > 128:
            raise VoiceProfileError("voice profile name must contain 1-128 characters")
        if provider not in {"chatterbox-local", "elevenlabs"}:
            raise VoiceProfileError("unsupported voice profile provider")
        expected = (
            "chatterbox-turbo" if provider == "chatterbox-local" else "eleven_multilingual_v2"
        )
        if value.get("engine") != expected:
            raise VoiceProfileError("voice profile engine does not match provider")
        consent = str(value.get("consent_record") or "")
        if len(consent) < 10 or len(consent) > 256:
            raise VoiceProfileError("voice profile requires a 10-256 character consent record")
        reference = value.get("reference")
        if reference is not None and reference not in {"reference.wav", "reference.mp3"}:
            raise VoiceProfileError("voice profile reference path is invalid")
        return dict(value)

    def _validate_new(self, profile_id: str, name: str, consent: str) -> None:
        self._validate_id(profile_id)
        if not name.strip() or len(name) > 128:
            raise VoiceProfileError("voice profile name must contain 1-128 characters")
        if len(consent.strip()) < 10 or len(consent) > 256:
            raise VoiceProfileError("consent record must contain 10-256 characters")

    @staticmethod
    def _validate_id(profile_id: str) -> None:
        if not _ID.fullmatch(profile_id):
            raise VoiceProfileError(
                "profile id must use 1-64 lowercase letters, numbers, '-' or '_'"
            )

    @staticmethod
    def _safe_name(member: zipfile.ZipInfo) -> PurePosixPath:
        path = PurePosixPath(member.filename.replace("\\", "/"))
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise VoiceProfileError("voice profile ZIP contains an unsafe path")
        if member.external_attr >> 16 & 0o170000 == 0o120000:
            raise VoiceProfileError("voice profile ZIP cannot contain links")
        return path
