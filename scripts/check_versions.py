#!/usr/bin/env python3
"""Fail when an active OpenMimicry package/app version drifts from the root."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _toml(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    root_project = _toml(ROOT / "pyproject.toml")["project"]
    assert isinstance(root_project, dict)
    expected = str(root_project["version"])
    observed: dict[str, str] = {"pyproject.toml": expected}

    for path in sorted((ROOT / "packages").glob("*/pyproject.toml")):
        project = _toml(path)["project"]
        assert isinstance(project, dict)
        observed[str(path.relative_to(ROOT))] = str(project["version"])
    backend_project = _toml(ROOT / "apps/backend/pyproject.toml")["project"]
    assert isinstance(backend_project, dict)
    observed["apps/backend/pyproject.toml"] = str(backend_project["version"])

    for relative in (
        "package.json",
        "apps/desktop/frontend/package.json",
        "apps/external-echo/package.json",
        "apps/desktop/src-tauri/tauri.conf.json",
    ):
        payload = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        observed[relative] = str(payload["version"])

    cargo = _toml(ROOT / "apps/desktop/src-tauri/Cargo.toml")["package"]
    assert isinstance(cargo, dict)
    observed["apps/desktop/src-tauri/Cargo.toml"] = str(cargo["version"])
    lock = _toml(ROOT / "apps/desktop/src-tauri/Cargo.lock")
    packages = lock.get("package")
    assert isinstance(packages, list)
    desktop = next(
        item
        for item in packages
        if isinstance(item, dict) and item.get("name") == "openmimicry-desktop"
    )
    observed["apps/desktop/src-tauri/Cargo.lock"] = str(desktop["version"])

    init_paths = [
        ROOT / "apps/backend/src/openmimicry_backend/__init__.py",
        *sorted((ROOT / "packages").glob("*/src/openmimicry/*/__init__.py")),
    ]
    pattern = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)
    for path in init_paths:
        match = pattern.search(path.read_text(encoding="utf-8"))
        if match:
            observed[str(path.relative_to(ROOT))] = match.group(1)

    mismatches = {path: version for path, version in observed.items() if version != expected}
    report = {
        "expected": expected,
        "checked": len(observed),
        "mismatches": mismatches,
        "passed": not mismatches,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
