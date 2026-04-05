
from __future__ import annotations

from pathlib import Path
from typing import Any
import threading
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
CHAR_DIR = ROOT / "characters"

_config_lock = threading.Lock()

def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def load_theme() -> dict[str, Any]:
    with _config_lock:
        return _load_yaml(CONFIG_DIR / "theme.yml")

def load_runtime() -> dict[str, Any]:
    with _config_lock:
        return _load_yaml(CONFIG_DIR / "runtime.yml")

def load_personality() -> dict[str, Any]:
    with _config_lock:
        return _load_yaml(CONFIG_DIR / "personality.yml")

def load_character(name: str) -> dict[str, Any]:
    with _config_lock:
        return _load_yaml(CHAR_DIR / name / "character.yml")
