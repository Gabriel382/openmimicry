from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient


def test_wake_name_is_updated_live_and_persisted(
    client: TestClient,
    wiring,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_config = tmp_path / "user.yaml"
    monkeypatch.setenv("OPENMIMICRY_USER_CONFIG", str(user_config))

    response = client.post("/voice/settings", json={"wake_name": "Octo"})

    assert response.status_code == 200
    assert response.json()["wake_names"] == ["Octo", "Hey Octo"]
    assert wiring.speech.wake_names == ["Hey Octo", "Octo"]
    persisted = yaml.safe_load(user_config.read_text(encoding="utf-8"))
    assert persisted["voice"]["stt"]["wake"]["names"] == ["Octo", "Hey Octo"]


def test_wake_name_rejects_punctuation_only(client: TestClient) -> None:
    response = client.post("/voice/settings", json={"wake_name": "!!!"})
    assert response.status_code == 422


def test_end_of_speech_pause_is_updated_live_and_persisted(
    client: TestClient,
    wiring,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_config = tmp_path / "user.yaml"
    monkeypatch.setenv("OPENMIMICRY_USER_CONFIG", str(user_config))

    response = client.post("/voice/settings", json={"post_speech_silence_duration": 1.4})

    assert response.status_code == 200
    assert response.json()["post_speech_silence_duration"] == 1.4
    assert wiring.speech.post_speech_silence_duration == 1.4
    persisted = yaml.safe_load(user_config.read_text(encoding="utf-8"))
    assert persisted["voice"]["stt"]["post_speech_silence_duration"] == 1.4


def test_end_of_speech_pause_is_bounded(client: TestClient) -> None:
    response = client.post("/voice/settings", json={"post_speech_silence_duration": 4.0})
    assert response.status_code == 422


def test_stt_quality_is_warmed_live_and_persisted(
    client: TestClient,
    wiring,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_config = tmp_path / "user.yaml"
    monkeypatch.setenv("OPENMIMICRY_USER_CONFIG", str(user_config))

    response = client.post("/voice/settings", json={"stt_model": "base.en"})

    assert response.status_code == 200
    assert response.json()["stt_model"] == "base.en"
    assert wiring.speech.stt_model == "base.en"
    persisted = yaml.safe_load(user_config.read_text(encoding="utf-8"))
    assert persisted["voice"]["stt"]["model"] == "base.en"
