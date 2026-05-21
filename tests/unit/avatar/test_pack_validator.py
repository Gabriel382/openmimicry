"""Unit tests for openmimicry.avatar.pack.validator."""

from __future__ import annotations

from pathlib import Path

import pytest
from openmimicry.avatar.pack import ValidationReport, validate_pack

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "packs"


def test_good_pack_passes() -> None:
    report = validate_pack(FIXTURES / "good_pack")
    assert report.ok is True
    assert report.errors == []
    # No speaking-fallback warnings because every state has speaking_frames.
    assert all("missing speaking_frames" not in w for w in report.warnings)


def test_missing_speaking_is_warning_not_error() -> None:
    report = validate_pack(FIXTURES / "missing_speaking")
    assert report.ok is True
    assert report.errors == []
    assert any("missing speaking_frames" in w for w in report.warnings)


def test_broken_manifest_reports_errors() -> None:
    report = validate_pack(FIXTURES / "broken_manifest")
    assert report.ok is False
    assert report.errors
    # ValidationError content surfaces.
    assert any(
        "schema validation" in e or "folder does not exist" in e
        for e in report.errors
    )


def test_missing_directory_reports_error(tmp_path: Path) -> None:
    report = validate_pack(tmp_path / "nope")
    assert report.ok is False
    assert any("does not exist" in e for e in report.errors)


def test_missing_pack_yaml_reports_error(tmp_path: Path) -> None:
    report = validate_pack(tmp_path)
    assert report.ok is False
    assert any("missing pack.yaml" in e for e in report.errors)


def test_summary_string() -> None:
    ok_report = ValidationReport(path="x", ok=True)
    assert "OK" in ok_report.summary()
    warn_report = ValidationReport(path="x", ok=True, warnings=["w"])
    assert "warning" in warn_report.summary()
    fail_report = ValidationReport(path="x", ok=False, errors=["e"])
    assert "FAIL" in fail_report.summary()
