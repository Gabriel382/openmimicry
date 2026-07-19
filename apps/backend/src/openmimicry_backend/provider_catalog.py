"""Bounded model discovery for the two built-in provider families."""

from __future__ import annotations

import asyncio
import json
from ipaddress import ip_address
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

__all__ = ["CatalogError", "discover_models"]


_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models?output_modalities=text"


class CatalogError(RuntimeError):
    """A safe, user-facing provider discovery failure."""


async def discover_models(
    provider: str,
    *,
    api_base: str | None = None,
    bearer_token: str | None = None,
) -> list[dict[str, Any]]:
    """Return a normalized, size-bounded model list.

    OpenRouter uses its fixed public model endpoint. Ollama discovery is
    restricted to loopback so this dashboard route cannot be turned into an
    SSRF primitive by a modified user overlay.
    """

    normalized = provider.strip().lower()
    if normalized == "openrouter":
        headers = {"Accept": "application/json", "User-Agent": "OpenMimicry/1.6"}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        payload = await asyncio.to_thread(_get_json, _OPENROUTER_MODELS_URL, headers)
        raw_models = payload.get("data", []) if isinstance(payload, dict) else []
        models: list[dict[str, Any]] = []
        for raw in raw_models:
            if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
                continue
            model_id = raw["id"]
            pricing = raw.get("pricing") if isinstance(raw.get("pricing"), dict) else {}
            models.append(
                {
                    "id": model_id,
                    "runtime_model": f"openrouter/{model_id}",
                    "name": str(raw.get("name") or model_id),
                    "context_length": raw.get("context_length"),
                    "pricing": {
                        "prompt": pricing.get("prompt"),
                        "completion": pricing.get("completion"),
                    },
                }
            )
        return sorted(models, key=lambda item: item["name"].casefold())

    if normalized == "ollama":
        base = (api_base or "http://127.0.0.1:11434").rstrip("/")
        _require_loopback_http(base)
        payload = await asyncio.to_thread(
            _get_json,
            f"{base}/api/tags",
            {"Accept": "application/json", "User-Agent": "OpenMimicry/1.6"},
        )
        raw_models = payload.get("models", []) if isinstance(payload, dict) else []
        models = []
        for raw in raw_models:
            if not isinstance(raw, dict):
                continue
            model_id = raw.get("model") or raw.get("name")
            if not isinstance(model_id, str) or not model_id:
                continue
            details = raw.get("details") if isinstance(raw.get("details"), dict) else {}
            models.append(
                {
                    "id": model_id,
                    "runtime_model": f"ollama_chat/{model_id}",
                    "name": model_id,
                    "size": raw.get("size"),
                    "parameter_size": details.get("parameter_size"),
                    "quantization": details.get("quantization_level"),
                }
            )
        return sorted(models, key=lambda item: item["name"].casefold())

    raise CatalogError(f"model discovery is not supported for provider {provider!r}")


def _require_loopback_http(base: str) -> None:
    parsed = urlparse(base)
    if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
        raise CatalogError("Ollama discovery requires a plain HTTP loopback URL")
    host = parsed.hostname.casefold()
    if host == "localhost":
        return
    try:
        if ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise CatalogError("Ollama discovery is restricted to localhost")


def _get_json(url: str, headers: dict[str, str]) -> Any:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=8.0) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"application/json", "text/json"}:
                raise CatalogError(f"provider returned unexpected content type {content_type!r}")
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise CatalogError(f"provider model discovery failed: {exc}") from exc
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise CatalogError("provider model response exceeded 8 MiB")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogError("provider returned invalid JSON") from exc
