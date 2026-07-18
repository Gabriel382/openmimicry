"""Persistent, shareable diagnostics for desktop/audio lifecycle failures."""

from __future__ import annotations

import io
import json
import logging
import os
import platform
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import metadata
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from uuid import uuid4

from openmimicry.core import AppConfig

__all__ = ["DiagnosticsSession", "build_diagnostic_bundle", "install_diagnostics"]


_log = logging.getLogger(__name__)
_PACKAGE_NAMES = (
    "openmimicry-backend",
    "openmimicry-core",
    "openmimicry-voice",
    "RealtimeSTT",
    "RealtimeTTS",
    "faster-whisper",
    "litellm",
    "fastapi",
    "uvicorn",
    "websockets",
    "pyaudio",
    "pyttsx3",
    "comtypes",
)


@dataclass(frozen=True)
class DiagnosticsSession:
    """Location and correlation ID for one backend process."""

    session_id: str
    started_at: str
    log_path: Path
    _handler: RotatingFileHandler = field(repr=False, compare=False)

    def flush(self) -> None:
        self._handler.flush()

    def close(self) -> None:
        """Flush and detach this session's file handler."""

        root = logging.getLogger()
        root.removeHandler(self._handler)
        self.flush()
        self._handler.close()


def install_diagnostics(data_dir: str) -> DiagnosticsSession:
    """Attach a rotating UTF-8 file handler to all stdlib lifecycle logs."""

    override = os.environ.get("OPENMIMICRY_DIAGNOSTICS_DIR")
    root_dir = Path(override).expanduser() if override else Path(data_dir).expanduser() / "logs"
    root_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    session_id = f"{started:%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    log_path = root_dir / f"openmimicry-{session_id}.log"

    handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=2,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)sZ %(levelname)s [%(threadName)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    logging.getLogger().addHandler(handler)
    session = DiagnosticsSession(
        session_id=session_id,
        started_at=started.isoformat(),
        log_path=log_path,
        _handler=handler,
    )
    _log.info(
        "Diagnostics session started: session=%s log=%s",
        session.session_id,
        session.log_path,
    )
    return session


def build_diagnostic_bundle(
    *,
    session: DiagnosticsSession,
    config: AppConfig,
    runtime_status: dict[str, Any],
) -> bytes:
    """Return a ZIP with logs and sanitized runtime metadata, never `.env`."""

    generated_at = datetime.now(timezone.utc).isoformat()
    metadata_payload = {
        "generated_at": generated_at,
        "session_id": session.session_id,
        "session_started_at": session.started_at,
        "platform": platform.platform(),
        "python": sys.version,
        "executable": sys.executable,
        "runtime_status": runtime_status,
        "packages": _package_versions(),
        "config": _safe_config(config),
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "README.txt",
            "OpenMimicry diagnostic bundle\n"
            f"Session: {session.session_id}\n"
            f"Generated: {generated_at}\n\n"
            "This bundle intentionally excludes .env files and API-key values. "
            "Review it before sharing if your model names, paths, or transcripts "
            "are sensitive.\n",
        )
        archive.writestr(
            "runtime.json",
            json.dumps(metadata_payload, indent=2, ensure_ascii=False, default=str),
        )
        for candidate in sorted(session.log_path.parent.glob(f"{session.log_path.name}*")):
            if candidate.is_file():
                archive.write(candidate, f"logs/{candidate.name}")
    return output.getvalue()


def _package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for package_name in _PACKAGE_NAMES:
        try:
            versions[package_name] = metadata.version(package_name)
        except metadata.PackageNotFoundError:
            versions[package_name] = None
    return versions


def _safe_config(config: AppConfig) -> dict[str, Any]:
    """Keep operational choices while omitting any future secret-like keys."""

    raw = config.model_dump(mode="json")

    def scrub(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: (
                    "<redacted>"
                    if any(
                        token in key.casefold()
                        for token in ("secret", "token", "password", "api_key")
                    )
                    and not key.casefold().endswith("_env")
                    else scrub(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [scrub(item) for item in value]
        return value

    return scrub(raw)
