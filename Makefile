PYTHON ?= python3
PROFILE ?= basic

ifeq ($(OS),Windows_NT)
	VENV_DIR := backend/.venv
	VENV_PYTHON := $(VENV_DIR)/Scripts/python.exe
	PNPM_CMD := pnpm.cmd
	CARGO_CMD := cargo
	RM_VENV := if exist backend\.venv rmdir /s /q backend\.venv
	SHELL_PY := python
else
	VENV_DIR := backend/.venv
	VENV_PYTHON := $(VENV_DIR)/bin/python
	PNPM_CMD := pnpm
	CARGO_CMD := cargo
	RM_VENV := rm -rf backend/.venv
	SHELL_PY := python3
endif

.PHONY: help install backend frontend dev desktop doctor clean \
        lint format typecheck test ci pre-commit-install \
        check-imports validate-packs install-workspace

.DEFAULT_GOAL := help

help:
	@echo "OpenMimicry - common targets"
	@echo ""
	@echo "  make install PROFILE=basic   Install workspace + selected profile"
	@echo "    PROFILES: basic | voice | threejs | live3d | unity | agent"
	@echo "              vision (optional, post-v0.2 — webcam + MediaPipe)"
	@echo "              full | full-vision | studio | dev"
	@echo "  make backend                 Run FastAPI backend (uvicorn)"
	@echo "  make frontend                Run Vite dev server"
	@echo "  make dev                     Hints to run backend + frontend"
	@echo "  make desktop                 cargo tauri dev"
	@echo "  make doctor                  Print environment checklist"
	@echo ""
	@echo "  make lint                    Ruff lint + format check"
	@echo "  make format                  Apply Ruff formatting"
	@echo "  make typecheck               Pyright"
	@echo "  make test                    pytest"
	@echo "  make ci                      lint + typecheck + check-imports + test"
	@echo "  make check-imports           Enforce no-cross-module-imports"
	@echo "  make validate-packs          Validate character packs"
	@echo "  make pre-commit-install      Install Git hooks"
	@echo "  make clean                   Remove venvs and build artefacts"

$(VENV_DIR):
	$(PYTHON) -m venv $(VENV_DIR)

install: install-workspace
	@echo "OpenMimicry installed (PROFILE=$(PROFILE))"

install-workspace: $(VENV_DIR)
	@echo "Installing dev tooling and workspace packages (PROFILE=$(PROFILE))"
	$(VENV_PYTHON) -m pip install --upgrade pip setuptools wheel
	$(VENV_PYTHON) -m pip install -e ".[dev]"
	$(VENV_PYTHON) -m pip install -e packages/openmimicry-core
	$(VENV_PYTHON) -m pip install -e packages/openmimicry-llm
	$(VENV_PYTHON) -m pip install -e packages/openmimicry-voice
	$(VENV_PYTHON) -m pip install -e packages/openmimicry-avatar
	$(VENV_PYTHON) -m pip install -e packages/openmimicry-tasks
	@# Optional, post-v0.2: webcam + MediaPipe gesture detection.
	@# Only installed when the user opts in via PROFILE=vision (or full-vision).
	@if [ "$(PROFILE)" = "vision" ] || [ "$(PROFILE)" = "full-vision" ]; then \
		if [ -d packages/openmimicry-vision ]; then \
			$(VENV_PYTHON) -m pip install -e packages/openmimicry-vision; \
		else \
			echo "PROFILE=$(PROFILE) requested vision but packages/openmimicry-vision/ is not landed yet (M13)."; \
		fi; \
	fi
	@if [ -f backend/requirements.txt ]; then \
		$(VENV_PYTHON) -m pip install -r backend/requirements.txt || true; \
	fi
	@if [ -d frontend ]; then \
		$(PNPM_CMD) install --frozen-lockfile || true; \
	fi

backend:
	cd backend && $(VENV_PYTHON) -m uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && $(PNPM_CMD) run dev

# Strict frontend install: frozen lockfile, refuse install scripts unless
# explicitly approved in pnpm-workspace.yaml. See .npmrc + SECURITY.md.
frontend-install:
	$(PNPM_CMD) install --frozen-lockfile

frontend-audit:
	$(PNPM_CMD) audit --prod --audit-level=moderate

frontend-approve-builds:
	$(PNPM_CMD) approve-builds

dev:
	@echo "Run these in separate terminals:"
	@echo "  make backend"
	@echo "  make frontend"

desktop:
	cd src-tauri && $(CARGO_CMD) tauri dev

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
	@if [ -f scripts/validate_pack.py ]; then \
		for pack in characters/*/; do \
			echo "Validating $$pack"; \
			$(SHELL_PY) scripts/validate_pack.py "$$pack" || exit 1; \
		done; \
	else \
		echo "scripts/validate_pack.py not present (M3 not landed yet); skipping"; \
	fi

test:
	$(SHELL_PY) -m pytest

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
