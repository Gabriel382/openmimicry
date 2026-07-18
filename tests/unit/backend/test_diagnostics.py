from __future__ import annotations

import json
import logging
import zipfile
from io import BytesIO

from openmimicry.core import AppConfig
from openmimicry_backend.diagnostics import (
    build_diagnostic_bundle,
    install_diagnostics,
)


def test_bundle_contains_lifecycle_log_and_excludes_environment_secret(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("OPENMIMICRY_DIAGNOSTICS_DIR", str(tmp_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "must-not-appear-in-bundle")
    session = install_diagnostics(str(tmp_path))
    try:
        logging.getLogger("openmimicry.test").warning("repeat-tts-marker")
        session.flush()
        payload = build_diagnostic_bundle(
            session=session,
            config=AppConfig(),
            runtime_status={"tts_adapter": "realtimetts", "socket_count": 2},
        )
    finally:
        session.close()

    assert b"must-not-appear-in-bundle" not in payload
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        names = archive.namelist()
        runtime = json.loads(archive.read("runtime.json"))
        log_name = next(name for name in names if name.startswith("logs/"))
        log_text = archive.read(log_name).decode("utf-8")

    assert runtime["session_id"] == session.session_id
    assert runtime["runtime_status"]["tts_adapter"] == "realtimetts"
    assert "repeat-tts-marker" in log_text
