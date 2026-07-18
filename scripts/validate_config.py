#!/usr/bin/env python3
"""Validate the base OpenMimicry configuration and its profile overlays."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from openmimicry.core.config import ConfigError, load

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_CONFIG = PROJECT_ROOT / "config" / "app.yaml"
PROFILES_DIR = PROJECT_ROOT / "config" / "profiles"


def _profile_names(selected: str | None) -> list[str | None]:
    if selected:
        return [selected]
    names = sorted(path.stem for path in PROFILES_DIR.glob("*.yaml"))
    return [None, *names]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate config/app.yaml and one or every config profile."
    )
    parser.add_argument(
        "--profile",
        help="Validate only this profile overlay; omit to validate the base and every profile.",
    )
    args = parser.parse_args(argv)

    reports: list[dict[str, object]] = []
    failed = False
    for profile in _profile_names(args.profile):
        label = profile or "<base>"
        try:
            config = load(BASE_CONFIG, env={}, profile=profile)
        except ConfigError as exc:
            failed = True
            reports.append({"profile": label, "valid": False, "error": str(exc)})
            continue
        reports.append(
            {
                "profile": label,
                "valid": True,
                "llm_adapter": ("switchboard" if config.llm.backends else config.llm.adapter),
                "llm_backend": config.llm.active_backend,
                "llm_model": (
                    config.llm.backends[config.llm.active_backend].model
                    if config.llm.backends and config.llm.active_backend
                    else config.llm.model
                ),
                "stt_adapter": config.voice.stt.adapter,
                "tts_adapter": config.voice.tts.adapter,
                "avatar_runtime": config.avatar.runtime,
            }
        )

    print(json.dumps({"configs": reports}, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
