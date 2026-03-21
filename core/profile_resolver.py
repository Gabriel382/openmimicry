"""Profile loading and dependency resolution."""

from __future__ import annotations

from pathlib import Path
import tomllib

from core.package_registry import PackageRegistry
from core.types import ProfileDefinition, ResolvedProfile
from core.validation import ConfigValidationError, validate_profile_definition, validate_runtime_settings


class ProfileResolver:
    """Resolves profile files into packages and merged runtime settings."""

    def __init__(self, profiles_dir: Path, registry: PackageRegistry, runtime_defaults_path: Path) -> None:
        self.profiles_dir = profiles_dir
        self.registry = registry
        self.runtime_defaults_path = runtime_defaults_path

    def load_profile(self, profile_name: str) -> tuple[ProfileDefinition, Path]:
        """Load a profile definition from a TOML file."""

        profile_path = self.profiles_dir / f"{profile_name}.toml"
        if not profile_path.exists():
            raise ConfigValidationError(f"Profile file not found: {profile_path}")

        data = tomllib.loads(profile_path.read_text(encoding="utf-8"))
        validate_profile_definition(data)
        return (
            ProfileDefinition(
                name=data["name"],
                description=data["description"],
                packs=list(data["packs"]),
                runtime_overrides=data.get("runtime_overrides", {}),
            ),
            profile_path,
        )

    def load_runtime_defaults(self) -> dict:
        """Load the default runtime settings file."""

        data = tomllib.loads(self.runtime_defaults_path.read_text(encoding="utf-8"))
        validate_runtime_settings(data)
        return data

    def resolve(self, profile_name: str) -> ResolvedProfile:
        """Resolve a profile including recursive package dependencies."""

        profile, profile_path = self.load_profile(profile_name)
        runtime_settings = self.load_runtime_defaults()
        runtime_settings.update(profile.runtime_overrides)
        runtime_settings["profile"] = profile.name
        validate_runtime_settings(runtime_settings)

        manifests = []
        extras_to_install: list[str] = []
        seen: set[str] = set()

        def visit(package_name: str) -> None:
            if package_name in seen:
                return
            seen.add(package_name)
            manifest = self.registry.get(package_name)
            for dependency in manifest.dependencies:
                visit(dependency)
            manifests.append(manifest)
            if manifest.python_extra and manifest.python_extra not in extras_to_install:
                extras_to_install.append(manifest.python_extra)

        for package_name in profile.packs:
            visit(package_name)

        return ResolvedProfile(
            profile=profile,
            manifests=manifests,
            extras_to_install=extras_to_install,
            merged_runtime_settings=runtime_settings,
            profile_path=profile_path,
        )
