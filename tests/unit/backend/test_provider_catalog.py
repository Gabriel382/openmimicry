from __future__ import annotations

import pytest
from openmimicry_backend import provider_catalog


async def test_openrouter_catalog_is_normalized_and_sorted(monkeypatch) -> None:
    monkeypatch.setattr(
        provider_catalog,
        "_get_json",
        lambda _url, _headers: {
            "data": [
                {"id": "z/model", "name": "Zulu", "pricing": {"prompt": "0.1"}},
                {"id": "a/model", "name": "Alpha", "context_length": 8192},
                {"name": "missing id"},
            ]
        },
    )

    models = await provider_catalog.discover_models("openrouter")

    assert [model["name"] for model in models] == ["Alpha", "Zulu"]
    assert models[0]["runtime_model"] == "openrouter/a/model"


@pytest.mark.parametrize(
    "base",
    [
        "https://127.0.0.1:11434",
        "http://192.168.1.20:11434",
        "http://example.com:11434",
        "http://user:pass@localhost:11434",
    ],
)
async def test_ollama_catalog_rejects_non_loopback_or_credentialed_urls(base: str) -> None:
    with pytest.raises(provider_catalog.CatalogError):
        await provider_catalog.discover_models("ollama", api_base=base)


async def test_ollama_catalog_accepts_loopback_and_normalizes_models(monkeypatch) -> None:
    calls: list[str] = []

    def fake_get(url: str, _headers):
        calls.append(url)
        return {
            "models": [
                {
                    "name": "gpt-oss:20b",
                    "size": 42,
                    "details": {"parameter_size": "20B", "quantization_level": "Q4"},
                }
            ]
        }

    monkeypatch.setattr(provider_catalog, "_get_json", fake_get)
    models = await provider_catalog.discover_models("ollama", api_base="http://localhost:11434")

    assert calls == ["http://localhost:11434/api/tags"]
    assert models[0]["runtime_model"] == "ollama_chat/gpt-oss:20b"
    assert models[0]["parameter_size"] == "20B"
