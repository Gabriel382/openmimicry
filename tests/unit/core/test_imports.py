"""Import-hygiene test — runs ``scripts/check_imports.py`` and asserts clean."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "check_imports.py"


def test_check_imports_clean() -> None:
    assert SCRIPT.exists(), f"missing {SCRIPT}"
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"scripts/check_imports.py failed:\n{result.stdout}\n{result.stderr}"
    )


def test_ergonomic_top_level_imports() -> None:
    """``from openmimicry.core import ...`` is the supported one-stop shop."""
    from openmimicry.core import (
        AppConfig,
        AvatarDirective,
        EventBus,
        LLMAdapter,
        RuntimeEvent,
        STTAdapter,
        TaskRuntimeAdapter,
        TTSAdapter,
    )

    assert AppConfig().schema_version == 1
    assert callable(EventBus)
    # Protocols are types; assert they are isinstance-checkable.
    assert hasattr(LLMAdapter, "__instancecheck__")
    assert hasattr(STTAdapter, "__instancecheck__")
    assert hasattr(TTSAdapter, "__instancecheck__")
    assert hasattr(TaskRuntimeAdapter, "__instancecheck__")
    # Sanity-spot the schema imports.
    assert AvatarDirective(state="idle").state == "idle"
    assert RuntimeEvent is not None
