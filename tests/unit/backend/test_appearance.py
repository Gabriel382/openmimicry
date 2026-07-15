from __future__ import annotations

from openmimicry_backend.appearance import AppearanceConfig, load_appearance


def test_missing_appearance_file_uses_safe_defaults(tmp_path) -> None:
    config = load_appearance(tmp_path / "missing.yml")
    assert config.windows.overlay.always_on_top is True
    assert config.windows.controls.height == 46
    assert config.windows.composer.height == 54
    assert config.layout.composer_gap == 6
    assert config.behaviour.bubble.ms_per_character == 55


def test_appearance_values_are_validated_and_loaded(tmp_path) -> None:
    path = tmp_path / "theme.yml"
    path.write_text(
        """
windows:
  overlay:
    width: 512
    height: 640
behaviour:
  bubble:
    base_ms: 4000
    ms_per_character: 70
    max_ms: 45000
""",
        encoding="utf-8",
    )
    config = load_appearance(path)
    assert isinstance(config, AppearanceConfig)
    assert config.windows.overlay.width == 512
    assert config.behaviour.bubble.base_ms == 4000
