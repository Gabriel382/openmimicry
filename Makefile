PYTHON ?= python3
PROFILE ?= basic

ifeq ($(OS),Windows_NT)
	VENV_DIR := .venv
	VENV_PYTHON := $(VENV_DIR)/Scripts/python.exe
	PNPM_CMD := pnpm.cmd
	CARGO_CMD := cargo
	RM_VENV := if exist .venv rmdir /s /q .venv
	SHELL_PY := python
else
	VENV_DIR := .venv
	VENV_PYTHON := $(VENV_DIR)/bin/python
	PNPM_CMD := pnpm
	CARGO_CMD := cargo
	RM_VENV := rm -rf .venv
	SHELL_PY := python3
endif

.PHONY: help install backend backend-prod frontend frontend-install \
        frontend-build frontend-test frontend-typecheck \
        frontend-audit frontend-approve-builds \
        dev desktop desktop-build desktop-test doctor clean \
        docker-build docker-up docker-up-frontend docker-down \
        cleanup-legacy release-preview \
        lint format typecheck test ci pre-commit-install \
        check-imports validate-packs install-workspace \
        m1-demo m1-demo-ollama m2-demo m2-demo-barge-in

.DEFAULT_GOAL := help

help:
	@echo "OpenMimicry — common targets"
	@echo ""
	@echo "Setup"
	@echo "  make install PROFILE=basic         Install workspace + selected profile"
	@echo "    PROFILES: basic | voice | threejs | live3d | unity | agent"
	@echo "              vision (optional — webcam + MediaPipe, off by default)"
	@echo "              full | full-vision | studio | dev"
	@echo "  make doctor                        Print environment checklist"
	@echo "  make cleanup-legacy                Remove v0.x prototype dirs"
	@echo ""
	@echo "Run"
	@echo "  make backend                       FastAPI backend on :8000 (reload)"
	@echo "  make backend-prod                  FastAPI backend bound to 0.0.0.0"
	@echo "  make frontend                      Vite dev server (:5173)"
	@echo "  make dev                           Hint for two-terminal dev loop"
	@echo "  make desktop                       cargo tauri dev (overlay + panel)"
	@echo ""
	@echo "Docker"
	@echo "  make docker-build                  Build backend + frontend-dev images"
	@echo "  make docker-up                     Compose up backend only"
	@echo "  make docker-up-frontend            Compose up backend + frontend-dev"
	@echo "  make docker-down                   Compose down"
	@echo ""
	@echo "Tests + quality"
	@echo "  make test                          pytest (Python)"
	@echo "  make frontend-test                 Vitest"
	@echo "  make desktop-test                  cargo fmt + clippy + test"
	@echo "  make lint                          Ruff lint + format check"
	@echo "  make format                        Apply Ruff formatting"
	@echo "  make typecheck                     Pyright"
	@echo "  make check-imports                 Enforce no cross-module imports"
	@echo "  make validate-packs                Validate character packs"
	@echo "  make ci                            lint + typecheck + check-imports + test"
	@echo "  make pre-commit-install            Install Git hooks"
	@echo ""
	@echo "Smoke demos (no real network)"
	@echo "  make m1-demo                       Mock LLM stream"
	@echo "  make m1-demo-ollama                Stream from a local Ollama model"
	@echo "  make m2-demo                       Drive SpeechController + mock STT/TTS"
	@echo "  make m2-demo-barge-in              Exercise the barge-in path"
	@echo ""
	@echo "Release"
	@echo "  make release-preview               Show the v1.0.0 publish plan"
	@echo "  make clean                         Remove venv + build artefacts"

$(VENV_DIR):
	$(PYTHON) -m venv $(VENV_DIR)

install: install-workspace
	@echo "OpenMimicry installed (PROFILE=$(PROFILE))"

install-workspace: $(VENV_DIR)
	@echo "Installing workspace packages + dev tooling (PROFILE=$(PROFILE))"
	$(VENV_PYTHON) -m pip install --upgrade pip setuptools wheel
	@# Install workspace packages FIRST in editable mode so the root
	@# `pip install -e .[dev]` step below sees them as already-satisfied.
	@# Reversing this order makes pip try to resolve `openmimicry-core`
	@# from PyPI, which fails (we haven't published yet).
	$(VENV_PYTHON) -m pip install -e packages/openmimicry-core
	$(VENV_PYTHON) -m pip install -e packages/openmimicry-llm
	$(VENV_PYTHON) -m pip install -e packages/openmimicry-voice
	$(VENV_PYTHON) -m pip install -e packages/openmimicry-avatar
	$(VENV_PYTHON) -m pip install -e packages/openmimicry-tasks
	@# M6 backend application (depends on every package above).
	@if [ -f apps/backend/pyproject.toml ]; then \
		$(VENV_PYTHON) -m pip install -e apps/backend; \
	fi
	@# Root project + dev tooling (ruff, pyright, pytest, pre-commit, …).
	$(VENV_PYTHON) -m pip install -e ".[dev]"
	@# Optional, post-v0.2: webcam + MediaPipe gesture detection.
	@# Only installed when the user opts in via PROFILE=vision (or full-vision).
	@if [ "$(PROFILE)" = "vision" ] || [ "$(PROFILE)" = "full-vision" ]; then \
		if [ -d packages/openmimicry-vision ]; then \
			$(VENV_PYTHON) -m pip install -e packages/openmimicry-vision; \
		else \
			echo "PROFILE=$(PROFILE) requested vision but packages/openmimicry-vision/ is not landed yet (M13)."; \
		fi; \
	fi
	@if [ -d apps/desktop/frontend ]; then \
		$(PNPM_CMD) install --frozen-lockfile || true; \
	fi

# ---------------------------------------------------------------------------
# Run targets — every command targets the new packages/ + apps/ layout.
# Run `bash scripts/cleanup-legacy.sh --apply` to remove the v0.x prototype
# directories if you still have them on disk.
# ---------------------------------------------------------------------------

backend:
	$(VENV_PYTHON) -m uvicorn openmimicry_backend.main:app --reload --port 8000

backend-prod:
	$(VENV_PYTHON) -m uvicorn openmimicry_backend.main:app --host 0.0.0.0 --port 8000

frontend:
	$(PNPM_CMD) --filter @openmimicry/desktop-frontend dev

# Strict frontend install: frozen lockfile, refuse install scripts unless
# explicitly approved in pnpm-workspace.yaml. See .npmrc + SECURITY.md.
frontend-install:
	$(PNPM_CMD) install --frozen-lockfile

frontend-build:
	$(PNPM_CMD) --filter @openmimicry/desktop-frontend build

frontend-test:
	$(PNPM_CMD) --filter @openmimicry/desktop-frontend test

frontend-typecheck:
	$(PNPM_CMD) --filter @openmimicry/desktop-frontend typecheck

frontend-audit:
	$(PNPM_CMD) audit --prod --audit-level=moderate

frontend-approve-builds:
	$(PNPM_CMD) approve-builds

dev:
	@echo "Run these in separate terminals:"
	@echo "  make backend"
	@echo "  make frontend"

desktop:
	cd apps/desktop/src-tauri && $(CARGO_CMD) tauri dev

desktop-build:
	cd apps/desktop/src-tauri && $(CARGO_CMD) tauri build

desktop-test:
	cd apps/desktop/src-tauri && $(CARGO_CMD) fmt --check && $(CARGO_CMD) clippy -- -D warnings && $(CARGO_CMD) test

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

docker-build:
	docker compose build

docker-up:
	docker compose up backend

docker-up-frontend:
	docker compose --profile dev up

docker-down:
	docker compose down

# ---------------------------------------------------------------------------
# Cleanup + release prep
# ---------------------------------------------------------------------------

cleanup-legacy:
	bash scripts/cleanup-legacy.sh --apply

release-preview:
	@echo "v1.0.0 publish plan (dry run)"
	@echo "  1. git tag v1.0.0 && git push origin v1.0.0"
	@echo "  2. GitHub release workflow (.github/workflows/release.yml) picks it up"
	@echo "  3. Manual: pnpm --filter @openmimicry/desktop-frontend build"
	@echo "  4. Manual: cd apps/desktop/src-tauri && cargo tauri build"
	@echo "  5. Attach build artefacts to the GitHub release"
	@echo "See CONTRIBUTING.md > Releases."

lint:
	$(SHELL_PY) -m ruff check .
	$(SHELL_PY) -m ruff format --check .

format:
	$(SHELL_PY) -m ruff format .
	$(SHELL_PY) -m ruff check --fix .

typecheck:
	$(SHELL_PY) -m pyright

check-imports:
	$(SHELL_PY) scripts/check_imports.py

validate-packs:
	@if [ -d characters ]; then \
		$(SHELL_PY) scripts/validate_pack.py characters/; \
	else \
		echo "no characters/ directory; skipping pack validation"; \
	fi

test:
	$(SHELL_PY) -m pytest

# ---------------------------------------------------------------------------
# M1 smoke demos -- no backend required.
# ---------------------------------------------------------------------------
PROMPT ?= Say hello in one short sentence.
LLM_MODEL ?= ollama/llama3.1

m1-demo:
	$(SHELL_PY) scripts/m1_demo.py --prompt "$(PROMPT)"

m1-demo-ollama:
	$(SHELL_PY) scripts/m1_demo.py --model "$(LLM_MODEL)" --prompt "$(PROMPT)"

# M2 smoke demos -- mock STT/TTS, no audio device required.
M2_TEXT ?= Hello from the voice mock.
M2_PTT_TEXT ?= hello from the user

m2-demo:
	$(SHELL_PY) scripts/m2_demo.py --text "$(M2_TEXT)" --ptt-text "$(M2_PTT_TEXT)"

m2-demo-barge-in:
	$(SHELL_PY) scripts/m2_demo.py --barge-in --skip-ptt --skip-wake

ci: lint typecheck check-imports test
	@echo "make ci: OK"

pre-commit-install:
	$(SHELL_PY) -m pre_commit install
	$(SHELL_PY) -m pre_commit install --hook-type commit-msg

doctor:
	$(SHELL_PY) scripts/doctor.py

clean:
	$(RM_VENV)
	rm -rf packages/*/build packages/*/dist packages/*/*.egg-info 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache 2>/dev/null || true
