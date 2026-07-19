#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ -f .env ]]; then
  while IFS='=' read -r key value; do
    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    if [[ ${#value} -ge 2 ]] && {
      [[ "${value:0:1}" == '"' && "${value: -1}" == '"' ]] ||
      [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]
    }; then
      value="${value:1:${#value}-2}"
    fi
    export "$key=$value"
  done < .env
fi

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "OPENROUTER_API_KEY is missing. Copy .env.example to .env and add your key." >&2
  exit 1
fi

python_path="$repo_root/.venv/bin/python"
runtime_installer="$repo_root/scripts/install_chatterbox_runtime.py"

if [[ ! -x "$python_path" ]] ||
   ! "$python_path" "$runtime_installer" --python "$python_path" --check-only; then
  make install PROFILE=openrouter-chatterbox
fi

"$python_path" "$runtime_installer" --python "$python_path" --check-only

marker="$HOME/.openmimicry/chatterbox-preflight-v1.6.2.ok"
if [[ "${OPENMIMICRY_CHATTERBOX_PREFLIGHT:-}" == "force" || ! -f "$marker" ]]; then
  echo "Loading and caching Chatterbox Turbo. The first run can take several minutes..."
  "$python_path" -u -m openmimicry.voice.workers.chatterbox_job \
    --preflight --device auto
  mkdir -p "$(dirname "$marker")"
  printf '%s\n' "OpenMimicry v1.6.2 Chatterbox preflight passed" > "$marker"
fi

export OPENMIMICRY_PROFILE=openrouter-chatterbox
export OPENMIMICRY__VOICE__TTS__READINESS_TIMEOUT_S=180
export HF_HUB_DISABLE_SYMLINKS_WARNING=1

exec "$python_path" -m uvicorn openmimicry_backend.main:app --port 8000
