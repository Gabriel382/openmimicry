#!/usr/bin/env python3
"""Audit the installed dependency closure for an OpenMimicry profile.

This is a release-engineering guard, not legal advice. It intentionally fails
closed on missing or unrecognised license metadata in ``--strict`` mode.
"""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
import re
from collections import deque
from typing import Any

from packaging.requirements import Requirement

COMMERCIAL_SEEDS = (
    "openmimicry-backend",
    "openmimicry-core",
    "openmimicry-llm",
    "openmimicry-memory",
    "openmimicry-voice",
    "openmimicry-avatar",
    "openmimicry-tasks",
    "litellm",
    "faster-whisper",
    "numpy",
    "sounddevice",
)
COMMUNITY_SEEDS = (*COMMERCIAL_SEEDS, "piper-tts")
CHATTERBOX_SEEDS = (*COMMERCIAL_SEEDS, "chatterbox-tts")

_ALLOW_TOKENS = (
    "mit",
    "apache",
    "bsd",
    "isc",
    "python software foundation",
    "psf",
    "unlicense",
    "0bsd",
    "cc0",
    "mpl-2.0",
    "mozilla public license 2.0",
)
_DENY_TOKENS = (
    "agpl",
    "gpl",
    "lgpl",
    "non-commercial",
    "noncommercial",
    "research-only",
)


def _canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).casefold()


def _license_text(dist: metadata.Distribution) -> str:
    expression = dist.metadata.get("License-Expression")
    if expression:
        return expression.strip()
    classifiers = [
        value.split("::")[-1].strip()
        for value in (dist.metadata.get_all("Classifier") or [])
        if value.startswith("License ::")
    ]
    if classifiers:
        return " OR ".join(classifiers)
    declared = dist.metadata.get("License")
    if declared and declared.strip().casefold() not in {"unknown", "n/a"}:
        # Some wheels place every bundled license in this field. Preserve a
        # bounded value for review, but prefer SPDX/classifier metadata above.
        return declared.strip()[:4096]
    return "UNKNOWN"


def _status(license_text: str) -> str:
    lowered = license_text.casefold()
    alternatives = re.split(r"\s+or\s+", lowered)
    if len(alternatives) > 1 and any(
        any(token in alternative for token in _ALLOW_TOKENS)
        and not any(token in alternative for token in _DENY_TOKENS)
        for alternative in alternatives
    ):
        return "allowed"
    if any(token in lowered for token in _DENY_TOKENS):
        return "denied"
    if any(token in lowered for token in _ALLOW_TOKENS):
        return "allowed"
    return "review"


def _installed() -> dict[str, metadata.Distribution]:
    return {
        _canonical(dist.metadata.get("Name", "")): dist
        for dist in metadata.distributions()
        if dist.metadata.get("Name")
    }


def audit(seeds: tuple[str, ...]) -> dict[str, Any]:
    installed = _installed()
    queue = deque(_canonical(seed) for seed in seeds)
    visited: set[str] = set()
    records: list[dict[str, str]] = []
    missing: list[str] = []
    while queue:
        name = queue.popleft()
        if name in visited:
            continue
        visited.add(name)
        dist = installed.get(name)
        if dist is None:
            missing.append(name)
            continue
        license_text = _license_text(dist)
        records.append(
            {
                "name": dist.metadata.get("Name", name),
                "version": dist.version,
                "license": license_text,
                "status": _status(license_text),
            }
        )
        for raw_requirement in dist.requires or ():
            try:
                requirement = Requirement(raw_requirement)
            except Exception:
                continue
            # Profile extras are represented explicitly in the seed set. Do
            # not infer every optional dependency advertised by a package.
            if requirement.marker is not None:
                try:
                    if not requirement.marker.evaluate({"extra": ""}):
                        continue
                except Exception:
                    continue
            queue.append(_canonical(requirement.name))
    records.sort(key=lambda item: item["name"].casefold())
    return {
        "schema_version": 1,
        "records": records,
        "missing": sorted(missing),
        "denied": [item["name"] for item in records if item["status"] == "denied"],
        "review": [item["name"] for item in records if item["status"] == "review"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile", choices=("commercial", "community", "chatterbox"), default="commercial"
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    seeds = {
        "commercial": COMMERCIAL_SEEDS,
        "community": COMMUNITY_SEEDS,
        "chatterbox": CHATTERBOX_SEEDS,
    }[args.profile]
    report = audit(seeds)
    report["profile"] = args.profile
    report["passed"] = not report["denied"] and not report["review"] and not report["missing"]
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
