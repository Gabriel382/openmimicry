from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_voice_extra_installs_current_upstream_engine_extras() -> None:
    package = tomllib.loads(
        (ROOT / "packages/openmimicry-voice/pyproject.toml").read_text(encoding="utf-8")
    )
    extras = package["project"]["optional-dependencies"]

    assert "RealtimeSTT[faster-whisper]>=0.3" in extras["voice"]
    assert "RealtimeTTS[system]>=0.4" in extras["voice"]
    audioop_compat = "audioop-lts>=0.2.2; python_version >= '3.13'"
    assert audioop_compat in extras["realtimetts"]
    assert audioop_compat in extras["voice"]


def test_launcher_captures_native_stderr_before_checking_exit_code() -> None:
    script = (ROOT / "scripts/win/start-openrouter-voice.ps1").read_text(encoding="utf-8")

    assert "function Test-VoiceImports" in script
    assert '$ErrorActionPreference = "Continue"' in script
    assert "2>&1" in script
    assert "2>$null" not in script
    assert '"scripts\\check_voice_imports.py"' in script
    assert "-c $voiceImportCode" not in script
    assert '@"' not in script
    assert "still unavailable in .venv after installation" in script
    assert '& ".\\scripts\\win\\backend.bat" "--no-reload"' in script


def test_windows_backend_supports_voice_safe_no_reload_mode() -> None:
    script = (ROOT / "scripts/win/backend.bat").read_text(encoding="utf-8")

    assert 'if /i "%~1"=="--no-reload" goto :no_reload' in script
    no_reload = script.rsplit("\n:no_reload", maxsplit=1)[1]
    assert "openmimicry_backend.main:app --port 8000" in no_reload
    assert "--reload" not in no_reload


def test_voice_import_check_is_file_based_and_imports_public_classes() -> None:
    check = (ROOT / "scripts/check_voice_imports.py").read_text(encoding="utf-8")

    assert "from RealtimeSTT import AudioToTextRecorder" in check
    assert "from RealtimeTTS import SystemEngine, TextToAudioStream" in check
    assert 'print("RealtimeSTT/RealtimeTTS imports OK")' in check
