import yaml
from openmimicry_backend.user_settings import persist_wake_names


def test_persist_wake_names_is_additive_and_atomic(tmp_path) -> None:
    path = tmp_path / "config" / "user.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("avatar:\n  pack: custom\n", encoding="utf-8")

    persisted = persist_wake_names(["Octo", "Hey Octo"], path)
    loaded = yaml.safe_load(persisted.read_text(encoding="utf-8"))

    assert loaded["avatar"]["pack"] == "custom"
    assert loaded["voice"]["stt"]["wake"]["names"] == ["Octo", "Hey Octo"]
    assert not path.with_suffix(".yaml.tmp").exists()
