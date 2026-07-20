from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.validate_install_environment as validator


def _repo(path: Path, *, name: str = "openmimicry") -> Path:
    path.mkdir()
    (path / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    return path


def test_validator_refuses_a_different_project_root(tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path / "neo-olaf", name="neo-olaf")
    environment = tmp_path / ".venv"
    environment.mkdir()
    monkeypatch.setattr(validator.sys, "prefix", str(environment))

    with pytest.raises(RuntimeError, match="not an OpenMimicry repository root"):
        validator.validate_environment(repo, claim=True)


def test_validator_refuses_unclaimed_nonempty_environment(tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path / "openmimicry")
    environment = tmp_path / "foreign" / ".venv"
    environment.mkdir(parents=True)
    monkeypatch.setattr(validator.sys, "prefix", str(environment))
    monkeypatch.setattr(
        validator,
        "_non_bootstrap_distributions",
        lambda: ["paddlepaddle", "torch", "transformers"],
    )

    with pytest.raises(RuntimeError, match="refusing to modify an unclaimed") as error:
        validator.validate_environment(repo)

    assert "OPENMIMICRY_CLAIM_EXISTING_VENV=1" in str(error.value)
    assert not (environment / validator.MARKER_NAME).exists()


def test_explicit_claim_is_persistent_for_the_same_repo(tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path / "openmimicry")
    environment = tmp_path / "openmimicry-venv"
    environment.mkdir()
    monkeypatch.setattr(validator.sys, "prefix", str(environment))
    monkeypatch.setattr(
        validator,
        "_non_bootstrap_distributions",
        lambda: ["openmimicry-core"],
    )

    claimed = validator.validate_environment(repo, claim=True)
    owned = validator.validate_environment(repo)

    assert claimed["status"] == "claimed"
    assert owned["status"] == "owned"
    marker = json.loads((environment / validator.MARKER_NAME).read_text(encoding="utf-8"))
    assert Path(marker["repo_root"]) == repo.resolve()


def test_claim_for_one_checkout_cannot_be_reused_by_another(tmp_path, monkeypatch) -> None:
    first = _repo(tmp_path / "first")
    second = _repo(tmp_path / "second")
    environment = tmp_path / ".venv"
    environment.mkdir()
    monkeypatch.setattr(validator.sys, "prefix", str(environment))
    monkeypatch.setattr(validator, "_non_bootstrap_distributions", lambda: [])
    validator.validate_environment(first, claim=True)

    with pytest.raises(RuntimeError, match="belongs to"):
        validator.validate_environment(second, claim=True)
