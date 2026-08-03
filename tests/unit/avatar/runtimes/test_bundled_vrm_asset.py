"""Regression tests for the redistributable Octomimic VRM fixture."""

from __future__ import annotations

import json
import runpy
import struct
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[4]
PACK_DIR = ROOT / "characters" / "octomimic_vrm"
ASSET = PACK_DIR / "octomimic.vrm"
GENERATOR = ROOT / "scripts" / "assets" / "generate_octomimic_vrm.py"


def _gltf_json(payload: bytes) -> dict[str, Any]:
    magic, version, total_length = struct.unpack_from("<4sII", payload)
    assert magic == b"glTF"
    assert version == 2
    assert total_length == len(payload)
    json_length, json_type = struct.unpack_from("<II", payload, 12)
    assert json_type == 0x4E4F534A
    return json.loads(payload[20 : 20 + json_length])


def test_bundled_vrm_is_current_deterministic_generator_output() -> None:
    namespace = runpy.run_path(str(GENERATOR), run_name="openmimicry_vrm_generator")
    assert namespace["build_vrm"]() == ASSET.read_bytes()


def test_bundled_vrm_declares_runtime_states_and_permissive_license() -> None:
    document = _gltf_json(ASSET.read_bytes())
    extension = document["extensions"]["VRMC_vrm"]
    meta = extension["meta"]
    clip_names = {animation["name"] for animation in document["animations"]}

    assert extension["specVersion"] == "1.0"
    assert meta["commercialUsage"] == "corporation"
    assert meta["allowRedistribution"] is True
    assert meta["modification"] == "allowModificationRedistribution"
    assert {"idle", "listening", "thinking", "speaking", "happy", "error"} <= clip_names


def test_pack_manifest_points_to_checked_in_vrm() -> None:
    manifest = yaml.safe_load((PACK_DIR / "pack.yaml").read_text(encoding="utf-8"))

    assert manifest["kind"] == "vrm"
    assert manifest["license"] == "CC0-1.0"
    assert manifest["metadata"]["asset"] == {"kind": "vrm", "path": "octomimic.vrm"}
    assert ASSET.is_file()
    assert ASSET.stat().st_size > 20_000
