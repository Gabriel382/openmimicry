# Project settings
PYTHON ?= python3
VENV_DIR ?= .venv
VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip
PROFILE ?= basic

# Default target
.DEFAULT_GOAL := help

help:
	@echo "Available commands:"
	@echo "  make install PROFILE=basic     Create venv and install dependencies"
	@echo "  make run                       Run the project"
	@echo "  make doctor                    Check local environment"
	@echo "  make clean                     Remove cache/build artifacts"

# Create virtual environment if missing
$(VENV_DIR):
	$(PYTHON) -m venv $(VENV_DIR)

# Install project inside the virtual environment
# $(VENV_PYTHON) -m pip install --upgrade pip setuptools wheel
install: $(VENV_DIR)
	@echo "Installing OpenMimicry with PROFILE=$(PROFILE)"
	$(VENV_PIP) install -e ".[${PROFILE}]"

# Run the app through the virtual environment
run: $(VENV_DIR)
	$(VENV_PYTHON) scripts/run.py

# Basic diagnostics
doctor:
	@echo "Python: $$($(PYTHON) --version 2>/dev/null || echo missing)"
	@echo "Venv: $(VENV_DIR)"
	@test -d $(VENV_DIR) && echo "Virtual environment: OK" || echo "Virtual environment: MISSING"
	@test -f pyproject.toml && echo "pyproject.toml: OK" || echo "pyproject.toml: MISSING"
	@test -f .env.example && echo ".env.example: OK" || echo ".env.example: MISSING"

# Cleanup
clean:
	rm -rf $(VENV_DIR)
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +