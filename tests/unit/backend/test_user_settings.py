import yaml
from openmimicry_backend.user_settings import persist_voice_settings, persist_wake_names


def test_persist_wake_names_is_additive_and_atomic(tmp_path) -> None:
    path = tmp_path / "config" / "user.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("avatar:\n  pack: custom\n", encoding="utf-8")

    persisted = persist_wake_names(["Octo", "Hey Octo"], path)
    loaded = yaml.safe_load(persisted.read_text(encoding="utf-8"))

    assert loaded["avatar"]["pack"] == "custom"
    assert loaded["voice"]["stt"]["wake"]["names"] == ["Octo", "Hey Octo"]
    assert not path.with_suffix(".yaml.tmp").exists()


def test_persist_voice_settings_preserves_wake_name_when_only_pause_changes(tmp_path) -> None:
    path = tmp_path / "user.yaml"
    path.write_text("voice:\n  stt:\n    wake:\n      names: [Octo]\n", encoding="utf-8")

    persist_voice_settings(post_speech_silence_duration=1.3, path=path)
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert loaded["voice"]["stt"]["wake"]["names"] == ["Octo"]
    assert loaded["voice"]["stt"]["post_speech_silence_duration"] == 1.3
