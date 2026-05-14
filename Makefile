PYTHON ?= python3
PROFILE ?= basic

ifeq ($(OS),Windows_NT)
	VENV_DIR := backend/.venv
	VENV_PYTHON := $(VENV_DIR)/Scripts/python.exe
	NPM_CMD := npm.cmd
	CARGO_CMD := cargo
	RM_VENV := if exist backend\.venv rmdir /s /q backend\.venv
else
	VENV_DIR := backend/.venv
	VENV_PYTHON := $(VENV_DIR)/bin/python
	NPM_CMD := npm
	CARGO_CMD := cargo
	RM_VENV := rm -rf backend/.venv
endif

.PHONY: help install backend frontend dev desktop doctor clean

.DEFAULT_GOAL := help

help:
	@echo "make install PROFILE=basic"
	@echo "make backend"
	@echo "make frontend"
	@echo "make dev"
	@echo "make desktop"
	@echo "make doctor"
	@echo "make clean"

$(VENV_DIR):
	$(PYTHON) -m venv $(VENV_DIR)

install: $(VENV_DIR)
	@echo "Installing OpenMimicry with PROFILE=$(PROFILE)"
	$(VENV_PYTHON) -m pip install --upgrade pip setuptools wheel
	$(VENV_PYTHON) -m pip install -r backend/requirements.txt
	cd frontend && $(NPM_CMD) install
	@echo "Installation finished"

backend:
	cd backend && .venv/bin/python -m uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && $(NPM_CMD) run dev

dev:
	@echo "Run these in separate terminals:"
	@echo "make backend"
	@echo "make frontend"

desktop:
	cd src-tauri && $(CARGO_CMD) tauri dev

doctor:
	@echo "Checking Python..."
	-$(PYTHON) --version
	@echo "Checking backend venv..."
	-$(VENV_PYTHON) --version
	@echo "Checking Node..."
	-$(NPM_CMD) --version
	@echo "Checking Rust..."
	-$(CARGO_CMD) --version
	@echo "Checking Tauri CLI..."
	-$(CARGO_CMD) tauri --version
	@echo "Checking Ollama..."
	-ollama --version
	@echo "Checking Piper..."
	-piper --version

clean:
	$(RM_VENV)