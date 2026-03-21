"""Package registry and manifest loading utilities."""

from __future__ import annotations

import json
from pathlib import Path

from core.types import AddonManifest
from core.validation import ConfigValidationError, validate_manifest


class PackageRegistry:
    """Loads package manifests and exposes them by name."""

    def __init__(self, registry_path: Path) -> None:
        self.registry_path = registry_path
        self.root_dir = registry_path.parent
        self._manifest_paths = self._load_registry_index(registry_path)
        self._cache: dict[str, AddonManifest] = {}

    def _load_registry_index(self, registry_path: Path) -> dict[str, Path]:
        """Load the registry.json index."""

        raw = json.loads(registry_path.read_text(encoding="utf-8"))
        packages = raw.get("packages", {})
        if not packages:
            raise ConfigValidationError("Package registry is empty")
        return {name: self.root_dir / rel_path for name, rel_path in packages.items()}

    def get(self, package_name: str) -> AddonManifest:
        """Return a single package manifest."""

        if package_name in self._cache:
            return self._cache[package_name]

        manifest_path = self._manifest_paths.get(package_name)
        if manifest_path is None:
            raise ConfigValidationError(f"Unknown package '{package_name}'")

        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        validate_manifest(data)
        manifest = AddonManifest(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            category=data["category"],
            python_extra=data.get("python_extra"),
            dependencies=data.get("dependencies", []),
            runtime_enabled_by_default=bool(data.get("runtime_enabled_by_default", False)),
        )
        self._cache[package_name] = manifest
        return manifest

    def all(self) -> list[AddonManifest]:
        """Return all package manifests."""

        return [self.get(name) for name in sorted(self._manifest_paths.keys())]
