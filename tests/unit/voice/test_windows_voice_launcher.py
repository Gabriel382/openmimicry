from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_voice_extra_installs_isolated_runtime_dependencies() -> None:
    package = tomllib.loads(
        (ROOT / "packages/openmimicry-voice/pyproject.toml").read_text(encoding="utf-8")
    )
    extras = package["project"]["optional-dependencies"]

    assert "faster-whisper>=1.2.1" in extras["voice"]
    assert "piper-tts==1.4.2" in extras["piper-community"]
    assert not any("piper" in dependency for dependency in extras["voice"])
    assert "sounddevice>=0.5" in extras["voice"]
    assert "RealtimeSTT[faster-whisper]>=0.3" in extras["legacy-realtime"]


def test_launcher_captures_native_stderr_before_checking_exit_code() -> None:
    script = (ROOT / "scripts/win/start-openrouter-voice.ps1").read_text(encoding="utf-8")

    assert "function Invoke-NativeCapture" in script
    assert '$ErrorActionPreference = "Continue"' in script
    assert "2>&1" in script
    assert "2>$null" not in script
    assert '"scripts\\check_voice_imports.py"' in script
    assert "-c $voiceImportCode" not in script
    assert '@"' not in script
    assert "still unavailable after installation" in script
    assert "voice_doctor.py" in script
    assert "voice-preflight-v1.5.1.ok" in script
    assert "$voiceModel.onnx.json" in script
    assert "Get-NetTCPConnection -LocalPort $backendPort -State Listen" in script
    assert "Close the old OpenMimicry backend" in script
    assert '& ".\\scripts\\win\\backend.bat" "--no-reload"' in script
    assert "start-openrouter-chatterbox.ps1" not in script
    assert "OPENMIMICRY_VENV" in script


def test_standard_voice_launcher_detects_repairs_and_prewarms_chatterbox() -> None:
    script = (ROOT / "scripts/win/start-openrouter-voice.ps1").read_text(encoding="utf-8")

    assert "chatterbox-local" in script
    assert "OPENMIMICRY_USER_CONFIG" in script
    assert '"openrouter-chatterbox"' in script
    assert "install_chatterbox_runtime.py" in script
    assert '"--check-only"' in script
    assert '"openmimicry.voice.workers.chatterbox_job"' in script
    assert '"--preflight", "--device", "auto"' in script
    assert "chatterbox-preflight-v1.6.4.ok" in script
    assert 'OPENMIMICRY__VOICE__TTS__READINESS_TIMEOUT_S = "180"' in script
    assert '& ".\\scripts\\win\\backend.bat" "--no-reload"' in script
    assert not (ROOT / "scripts/win/start-openrouter-chatterbox.ps1").exists()


def test_windows_backend_supports_voice_safe_no_reload_mode() -> None:
    script = (ROOT / "scripts/win/backend.bat").read_text(encoding="utf-8")

    assert 'if /i "%~1"=="--no-reload" goto :no_reload' in script
    no_reload = script.rsplit("\n:no_reload", maxsplit=1)[1]
    assert "openmimicry_backend.main:app --port 8000" in no_reload
    assert "--reload" not in no_reload
    assert '"%~dp0\\..\\.."' in script
    assert "OPENMIMICRY_VENV" in script
    assert "python -m uvicorn" not in script


def test_windows_installer_is_repo_rooted_and_guards_environment_ownership() -> None:
    script = (ROOT / "scripts/win/install.bat").read_text(encoding="utf-8")

    assert '"%~dp0\\..\\.."' in script
    assert 'set "VENV=%REPO_ROOT%\\.venv"' in script
    assert "OPENMIMICRY_VENV" in script
    assert "validate_install_environment.py" in script
    assert "OPENMIMICRY_CLAIM_EXISTING_VENV" in script


def test_voice_import_check_is_file_based_and_imports_isolated_dependencies() -> None:
    check = (ROOT / "scripts/check_voice_imports.py").read_text(encoding="utf-8")

    assert "from faster_whisper import WhisperModel" in check
    assert "from piper import PiperVoice" in check
    assert "import sounddevice" in check
    assert "isolated voice imports OK" in check
