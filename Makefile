PYTHON ?= python3
VENV_DIR ?= .venv
VENV_PYTHON := $(VENV_DIR)/bin/python
PROFILE ?= basic
.DEFAULT_GOAL := help

help:
	@echo "Available commands:"
	@echo "  make install PROFILE=basic    Create venv and install selected profile"
	@echo "  make run PROFILE=basic        Run the minimal app entrypoint"
	@echo "  make validate PROFILE=basic   Validate and print resolved config"
	@echo "  make doctor                   Check local environment"
	@echo "  make clean                    Remove local caches and venv"

$(VENV_DIR):
	$(PYTHON) -m venv $(VENV_DIR)

install: $(VENV_DIR)
	@echo "Installing OpenMimicry with PROFILE=$(PROFILE)"
	OPENMIMICRY_PROFILE=$(PROFILE) $(VENV_PYTHON) scripts/install_profile.py --profile $(PROFILE)

run: $(VENV_DIR)
	OPENMIMICRY_PROFILE=$(PROFILE) $(VENV_PYTHON) scripts/run.py

validate: $(VENV_DIR)
	OPENMIMICRY_PROFILE=$(PROFILE) $(VENV_PYTHON) scripts/validate_config.py --profile $(PROFILE)

health: $(VENV_DIR)
	OPENMIMICRY_PROFILE=$(PROFILE) $(VENV_PYTHON) scripts/backend_health.py --profile $(PROFILE)

switch-test: $(VENV_DIR)
	OPENMIMICRY_PROFILE=$(PROFILE) $(VENV_PYTHON) scripts/test_backend_switch.py --profile $(PROFILE)

doctor:
	@echo "Python: $$($(PYTHON) --version 2>/dev/null || echo missing)"
	@test -f pyproject.toml && echo "pyproject.toml: OK" || echo "pyproject.toml: MISSING"
	@test -f apps/runtime.default.toml && echo "runtime.default.toml: OK" || echo "runtime.default.toml: MISSING"
	@test -f packs/registry.json && echo "packs/registry.json: OK" || echo "packs/registry.json: MISSING"
	@for profile in basic extended studio full; do \
		if [ -f profiles/$$profile.toml ]; then echo "profiles/$$profile.toml: OK"; else echo "profiles/$$profile.toml: MISSING"; fi; \
	done

clean:
	rm -rf $(VENV_DIR)
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +

avatar-demo:
	OPENMIMICRY_PROFILE=$(PROFILE) .venv/bin/python scripts/run_avatar_demo.py