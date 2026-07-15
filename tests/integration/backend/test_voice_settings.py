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
