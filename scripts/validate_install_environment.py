"""Claim or validate the virtual environment used by OpenMimicry installers.

The marker prevents an installer invoked from another repository from
silently upgrading/downgrading that repository's Python dependency graph.
Existing non-empty environments without a marker require an explicit one-time
claim after the user verifies that the environment belongs to OpenMimicry.
"""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

MARKER_NAME = ".openmimicry-owner.json"
BOOTSTRAP_DISTRIBUTIONS = {"pip", "setuptools", "wheel"}


def _project_name(repo_root: Path) -> str | None:
    try:
        document = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    value = document.get("project", {}).get("name")
    return str(value).strip().casefold() if value else None


def _non_bootstrap_distributions() -> list[str]:
    values = {
        str(distribution.metadata.get("Name") or "").strip()
        for distribution in metadata.distributions()
    }
    return sorted(
        value for value in values if value and value.casefold() not in BOOTSTRAP_DISTRIBUTIONS
    )


def validate_environment(repo_root: Path, *, claim: bool = False) -> dict[str, object]:
    repo_root = repo_root.expanduser().resolve()
    environment = Path(sys.prefix).resolve()
    marker = environment / MARKER_NAME

    if _project_name(repo_root) != "openmimicry":
        raise RuntimeError(
            f"{repo_root} is not an OpenMimicry repository root; refusing to modify {environment}"
        )

    if marker.is_file():
        try:
            existing = json.loads(marker.read_text(encoding="utf-8"))
            owner = Path(str(existing["repo_root"])).expanduser().resolve()
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"invalid environment ownership marker: {marker}") from exc
        if owner != repo_root:
            raise RuntimeError(
                f"virtual environment {environment} belongs to {owner}, not {repo_root}"
            )
        return {
            "ok": True,
            "status": "owned",
            "repo_root": str(repo_root),
            "environment": str(environment),
        }

    installed = _non_bootstrap_distributions()
    if installed and not claim:
        sample = ", ".join(installed[:12])
        suffix = " ..." if len(installed) > 12 else ""
        raise RuntimeError(
            "refusing to modify an unclaimed, non-empty virtual environment: "
            f"{environment}\nDetected packages: {sample}{suffix}\n"
            "If this environment belongs only to OpenMimicry, rerun once with "
            "OPENMIMICRY_CLAIM_EXISTING_VENV=1. Otherwise create/use a dedicated "
            "OpenMimicry checkout and virtual environment."
        )

    payload = {
        "schema_version": 1,
        "owner": "OpenMimicry",
        "repo_root": str(repo_root),
        "environment": str(environment),
        "python": str(Path(sys.executable).resolve()),
        "claimed_at": datetime.now(timezone.utc).isoformat(),
        "claimed_existing_environment": bool(installed),
    }
    temporary = marker.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(marker)
    return {"ok": True, "status": "claimed", **payload}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--claim", action="store_true")
    args = parser.parse_args()
    try:
        report = validate_environment(Path(args.repo_root), claim=args.claim)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, indent=2))
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
