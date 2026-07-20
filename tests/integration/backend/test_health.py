"""Integration test for ``GET /health``."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_health_returns_ok_with_mocks(client: TestClient) -> None:
    """With every adapter as a mock and no failures, ``ok`` is True."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["schema_version"] >= 1
    adapters = body["adapters"]
    assert "llm" in adapters
    assert "stt" in adapters
    assert "tts" in adapters
    assert "avatar" in adapters
    assert "tasks" in adapters
    # The mock LLM is "mock", the mock STT is "mock-stt", etc.
    assert adapters["llm"]["mock"] is True
    assert adapters["stt"]["mock-stt"] is True
    assert adapters["tts"]["mock-tts"] is True
    assert body["runtime"]["state"] == "ready"


def test_split_health_surfaces_report_live_ready_and_components(client: TestClient) -> None:
    live = client.get("/health/live")
    ready = client.get("/health/ready")
    components = client.get("/health/components")

    assert live.status_code == 200
    assert live.json()["live"] is True
    assert ready.status_code == 200
    assert ready.json()["ready"] is True
    assert components.status_code == 200
    assert "llm:mock" in components.json()["components"]


def test_health_reports_false_when_an_adapter_is_unhealthy(
    client: TestClient, wiring, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If an adapter's healthcheck returns False, ``ok`` flips to False."""

    async def _unhealthy() -> bool:
        return False

    monkeypatch.setattr(wiring.llm, "healthcheck", _unhealthy)

    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["adapters"]["llm"]["mock"] is False
    assert client.get("/health/ready").status_code == 503
