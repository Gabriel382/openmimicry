#!/usr/bin/env sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

venv_root=${OPENMIMICRY_VENV:-"$repo_root/.venv"}
case "$venv_root" in
  /*) ;;
  *) venv_root="$repo_root/$venv_root" ;;
esac
python_path="$venv_root/bin/python"
if [ ! -x "$python_path" ]; then
  make install PROFILE=openrouter-commercial
fi

if ! "$python_path" scripts/check_commercial_voice_imports.py; then
  make install PROFILE=openrouter-commercial
  "$python_path" scripts/check_commercial_voice_imports.py
fi

marker="${HOME}/.openmimicry/voice-preflight-v1.6.0-commercial.ok"
if [ "${OPENMIMICRY_VOICE_PREFLIGHT:-}" = "force" ] || [ ! -f "$marker" ]; then
  "$python_path" scripts/commercial_voice_doctor.py --stt-model medium.en --playback
  mkdir -p "$(dirname "$marker")"
  printf '%s\n' "OpenMimicry v1.6.0 commercial voice preflight passed" > "$marker"
fi

export OPENMIMICRY_PROFILE=openrouter-commercial
exec "$python_path" -m uvicorn openmimicry_backend.main:app --port 8000
