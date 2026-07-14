"""AppConfig loader unit tests."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from openmimicry.core.config import ConfigError, SchemaVersionError, diff_dicts, load
from openmimicry.core.schemas.app import SCHEMA_VERSION


def test_load_returns_defaults_when_no_file_or_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("OPENMIMICRY_CONFIG", "OPENMIMICRY_PROFILE"):
        monkeypatch.delenv(key, raising=False)
    cfg = load(path="/nonexistent/path.yaml", env={})
    # Default tree must be valid even without a YAML.
    assert cfg.schema_version == SCHEMA_VERSION
    assert cfg.app.log_level == "INFO"


def test_load_reads_yaml(tmp_path: Path) -> None:
    yaml = tmp_path / "app.yaml"
    yaml.write_text(
        dedent(
            """
            schema_version: 1
            app:
              log_level: DEBUG
            llm:
              adapter: mock
              model: mock/test
            """
        ).strip(),
        encoding="utf-8",
    )
    cfg = load(yaml, env={})
    assert cfg.app.log_level == "DEBUG"
    assert cfg.llm.adapter == "mock"


def test_env_override_wins(tmp_path: Path) -> None:
    yaml = tmp_path / "app.yaml"
    yaml.write_text("schema_version: 1\napp: { log_level: INFO }\n", encoding="utf-8")
    cfg = load(
        yaml,
        env={"OPENMIMICRY__APP__LOG_LEVEL": "WARNING"},
    )
    assert cfg.app.log_level == "WARNING"


def test_env_override_booleans_and_numbers(tmp_path: Path) -> None:
    yaml = tmp_path / "app.yaml"
    yaml.write_text("schema_version: 1\n", encoding="utf-8")
    cfg = load(
        yaml,
        env={
            "OPENMIMICRY__APP__TELEMETRY": "true",
            "OPENMIMICRY__LLM__TEMPERATURE": "0.2",
            "OPENMIMICRY__LLM__REQUEST_TIMEOUT_S": "30",
            "OPENMIMICRY__UI__OVERLAY__ALWAYS_ON_TOP": "no",
        },
    )
    assert cfg.app.telemetry is True
    assert cfg.llm.temperature == pytest.approx(0.2)
    assert cfg.llm.request_timeout_s == 30
    assert cfg.ui.overlay.always_on_top is False


def test_env_override_accepts_json_list(tmp_path: Path) -> None:
    yaml = tmp_path / "app.yaml"
    yaml.write_text("schema_version: 1\n", encoding="utf-8")
    cfg = load(
        yaml,
        env={"OPENMIMICRY__VOICE__STT__WAKE__NAMES": '["A","B"]'},
    )
    assert cfg.voice.stt.wake.names == ["A", "B"]


def test_profile_overlay_merges_on_top_of_base(tmp_path: Path) -> None:
    # Layout: cwd/config/app.yaml + cwd/config/profiles/<name>.yaml
    profile_dir = tmp_path / "config" / "profiles"
    profile_dir.mkdir(parents=True)
    base = tmp_path / "config" / "app.yaml"
    base.write_text(
        dedent(
            """
            schema_version: 1
            app: { log_level: INFO }
            llm: { adapter: litellm }
            """
        ).strip(),
        encoding="utf-8",
    )
    (profile_dir / "dev.yaml").write_text("llm: { adapter: mock }\n", encoding="utf-8")
    cwd_before = Path.cwd()
    import os

    os.chdir(tmp_path)
    try:
        cfg = load(env={"OPENMIMICRY_PROFILE": "dev"})
    finally:
        os.chdir(cwd_before)
    assert cfg.llm.adapter == "mock"
    assert cfg.app.log_level == "INFO"


def test_missing_profile_raises(tmp_path: Path) -> None:
    cwd_before = Path.cwd()
    import os

    (tmp_path / "config").mkdir()
    os.chdir(tmp_path)
    try:
        with pytest.raises(ConfigError):
            load(env={"OPENMIMICRY_PROFILE": "nope"})
    finally:
        os.chdir(cwd_before)


def test_invalid_yaml_raises_with_path_hint(tmp_path: Path) -> None:
    bad = tmp_path / "app.yaml"
    bad.write_text("schema_version: 1\nfoo: : :\n", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        load(bad, env={})
    assert str(bad) in (exc.value.where or "")


def test_top_level_must_be_mapping(tmp_path: Path) -> None:
    bad = tmp_path / "app.yaml"
    bad.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load(bad, env={})


def test_future_schema_version_raises(tmp_path: Path) -> None:
    yaml = tmp_path / "app.yaml"
    yaml.write_text("schema_version: 999\n", encoding="utf-8")
    with pytest.raises(SchemaVersionError):
        load(yaml, env={})


def test_validation_error_surfaces_as_config_error(tmp_path: Path) -> None:
    yaml = tmp_path / "app.yaml"
    yaml.write_text(
        dedent(
            """
            schema_version: 1
            app:
              log_level: NOPE
            """
        ).strip(),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load(yaml, env={})


def test_diff_dicts_only_changed_leaves() -> None:
    before = {"a": 1, "b": {"c": 2, "d": 3}}
    after = {"a": 1, "b": {"c": 4, "d": 3}, "e": 5}
    diff = diff_dicts(before, after)
    assert diff == {"b": {"c": 4}, "e": 5}


def test_diff_dicts_empty_when_equal() -> None:
    assert diff_dicts({"a": 1}, {"a": 1}) == {}
