#!/usr/bin/env python3
"""Static import-hygiene checker for OpenMimicry's parallel-execution rules.

The rule (from `docs/parallel_execution.md` §3): a module's production source
may import from `openmimicry.core.*` and from its own package. It MUST NOT import
from sibling `openmimicry-*` packages directly. Tests and `mocks.py` files are
exempt. `apps/backend/src/openmimicry_backend/wiring.py` is the single allowed
exception because it is, by design, the only assembly point.

Exits 0 on clean tree, 1 on violations. Prints every violation with file:line.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Sibling openmimicry-* packages that production source may not import each
# other's modules from.
SIBLING_PACKAGES: frozenset[str] = frozenset(
    {"openmimicry.llm", "openmimicry.voice", "openmimicry.avatar", "openmimicry.tasks"}
)

# Paths whose production source we check.
PACKAGE_SOURCE_ROOTS: tuple[Path, ...] = (
    REPO_ROOT / "packages" / "openmimicry-llm" / "src",
    REPO_ROOT / "packages" / "openmimicry-voice" / "src",
    REPO_ROOT / "packages" / "openmimicry-avatar" / "src",
    REPO_ROOT / "packages" / "openmimicry-tasks" / "src",
)

# Files that are allowed to break the rule (because that's their job).
ALLOWLIST: frozenset[Path] = frozenset(
    {
        REPO_ROOT / "apps" / "backend" / "src" / "openmimicry_backend" / "wiring.py",
    }
)


def _allowed_for_file(py_file: Path) -> frozenset[str]:
    """Return the set of sibling-package prefixes this file may import from."""
    # mocks.py and any test file may import any sibling for fixture purposes.
    if py_file.name == "mocks.py" or "tests" in py_file.parts:
        return SIBLING_PACKAGES
    # Each package may, of course, import from itself.
    own_pkg = _own_package_prefix(py_file)
    return frozenset({own_pkg}) if own_pkg else frozenset()


def _own_package_prefix(py_file: Path) -> str | None:
    """Return e.g. 'openmimicry.llm' if `py_file` lives in that package's src tree."""
    try:
        rel = py_file.relative_to(REPO_ROOT)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 4 or parts[0] != "packages" or parts[2] != "src":
        return None
    name = parts[1]  # 'openmimicry-llm'
    if not name.startswith("openmimicry-"):
        return None
    suffix = name[len("openmimicry-") :]
    return f"openmimicry.{suffix}"


def _violating_imports(py_file: Path) -> list[tuple[int, str]]:
    """Return (lineno, dotted_name) tuples for every disallowed sibling import."""
    if py_file in ALLOWLIST:
        return []
    allowed = _allowed_for_file(py_file)
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    except SyntaxError as exc:
        return [(exc.lineno or 0, f"syntax-error: {exc.msg}")]

    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)

        for mod in modules:
            for sibling in SIBLING_PACKAGES:
                if mod == sibling or mod.startswith(sibling + "."):
                    if sibling in allowed:
                        break
                    violations.append((node.lineno, mod))
                    break
    return violations


def main() -> int:
    failures: list[str] = []
    for root in PACKAGE_SOURCE_ROOTS:
        if not root.exists():
            continue
        for py_file in sorted(root.rglob("*.py")):
            for lineno, mod in _violating_imports(py_file):
                rel = py_file.relative_to(REPO_ROOT)
                failures.append(f"{rel}:{lineno}: forbidden sibling import: {mod}")

    if failures:
        print("Import hygiene violations:", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
        print(
            "\nProduction source under packages/openmimicry-<X>/src may only "
            "import from openmimicry.core.* and its own package.\n"
            "See docs/parallel_execution.md §3.",
            file=sys.stderr,
        )
        return 1
    print("scripts/check_imports.py: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
