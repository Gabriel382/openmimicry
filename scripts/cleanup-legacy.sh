#!/usr/bin/env bash
# OpenMimicry v1.0 — one-shot legacy-tree cleanup.
#
# Removes the prototype directories that have been superseded by the
# `packages/` and `apps/` layout, plus stale milestone notes and dev
# caches. Re-runnable: missing paths are silently skipped.
#
# Usage (from the repo root):
#   bash scripts/cleanup-legacy.sh           # show what would be removed
#   bash scripts/cleanup-legacy.sh --apply   # actually delete

set -euo pipefail

apply=0
for arg in "$@"; do
    case "$arg" in
        --apply|-y) apply=1 ;;
        --help|-h)
            sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "unknown arg: $arg" >&2; exit 2 ;;
    esac
done

# Legacy prototype dirs replaced by the new layout.
legacy_dirs=(
    "avatar"        # superseded by packages/openmimicry-avatar
    "backend"       # superseded by apps/backend
    "backends"      # legacy adapter sketch
    "core"          # superseded by packages/openmimicry-core
    "frontend"      # superseded by apps/desktop/frontend
    "src-tauri"     # superseded by apps/desktop/src-tauri
    "tts"           # superseded by packages/openmimicry-voice
    "packs"         # legacy character-pack layout
    "profiles"      # legacy profile dir (now under config/profiles)
)

# Caches + build artefacts that shouldn't be checked in. .gitignore
# covers them going forward; this sweep is for the in-tree copies.
cache_dirs=(
    "node_modules"
    "openmimicry.egg-info"
    ".pytest_cache"
    ".ruff_cache"
    ".venv"
)

# Loose dev caches sometimes left by pytest-xdist.
cache_glob=(
    "pytest-cache-files-*"
)

# Stale root-level docs that landed before the milestone module
# briefs in docs/modules/ existed.
stale_files=(
    ":USERPROFILE.wslconfig"
    "realtimesst.log"
    "Milestone.md"
    "MILESTONE5_INTEGRATION.md"
    "PATCH_NOTES.md"
    "README_EMOTION_SPEAKING_PATCH.md"
    "README_MILESTONE6.md"
    "README_MILESTONE6_5.md"
    "README_MILESTONE8.md"
)

note() {
    if [ "$apply" -eq 1 ]; then
        echo "  rm -rf $1"
    else
        echo "  would rm: $1"
    fi
}

for d in "${legacy_dirs[@]}" "${cache_dirs[@]}"; do
    if [ -e "$d" ]; then
        note "$d"
        [ "$apply" -eq 1 ] && rm -rf -- "$d"
    fi
done

for pattern in "${cache_glob[@]}"; do
    for match in $pattern; do
        if [ -e "$match" ]; then
            note "$match"
            [ "$apply" -eq 1 ] && rm -rf -- "$match"
        fi
    done
done

for f in "${stale_files[@]}"; do
    if [ -e "$f" ]; then
        note "$f"
        [ "$apply" -eq 1 ] && rm -f -- "$f"
    fi
done

if [ "$apply" -eq 0 ]; then
    echo ""
    echo "Dry run. Re-run with --apply to actually delete."
else
    echo ""
    echo "Cleanup complete. Review with: git status"
fi
