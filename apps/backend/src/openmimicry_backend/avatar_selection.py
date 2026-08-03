"""Character-pack/runtime compatibility rules shared by startup and routes."""

from __future__ import annotations

__all__ = ["runtime_for_pack_kind"]


def runtime_for_pack_kind(kind: str) -> str | None:
    """Return the canonical built-in runtime for a manifest kind."""

    if kind == "sprite2d":
        return "sprite2d"
    if kind in {"vrm", "gltf", "threejs"}:
        return "threejs"
    if kind == "unity":
        return "unity"
    if kind == "external":
        return "external"
    return None
