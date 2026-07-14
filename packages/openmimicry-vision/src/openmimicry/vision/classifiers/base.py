"""Classifier-registry plumbing — entry-point lookup with typed errors."""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any

__all__ = [
    "GESTURE_GROUP",
    "MOVEMENT_GROUP",
    "ClassifierUnavailable",
    "available_gesture_classifiers",
    "available_movement_classifiers",
    "load_gesture_classifier",
    "load_movement_classifier",
]


GESTURE_GROUP = "openmimicry.contracts.vision_gesture_classifier"
MOVEMENT_GROUP = "openmimicry.contracts.vision_movement_classifier"


class ClassifierUnavailable(RuntimeError):
    """Raised when a classifier factory can't satisfy its deps."""


def _select(group: str) -> list[Any]:
    try:
        return list(entry_points(group=group))
    except TypeError:
        return list(entry_points().get(group, []))  # type: ignore[attr-defined]


def available_gesture_classifiers() -> list[str]:
    return sorted(ep.name for ep in _select(GESTURE_GROUP))


def available_movement_classifiers() -> list[str]:
    return sorted(ep.name for ep in _select(MOVEMENT_GROUP))


def load_gesture_classifier(name: str, **kwargs: Any) -> Any:
    return _load(name, GESTURE_GROUP, **kwargs)


def load_movement_classifier(name: str, **kwargs: Any) -> Any:
    return _load(name, MOVEMENT_GROUP, **kwargs)


def _load(name: str, group: str, **kwargs: Any) -> Any:
    eps = _select(group)
    for ep in eps:
        if ep.name == name:
            try:
                factory = ep.load()
            except Exception as exc:
                raise ClassifierUnavailable(f"{group} {name!r} failed to load: {exc}") from exc
            return factory(**kwargs)
    raise ClassifierUnavailable(
        f"{group} {name!r} not registered (available: {[ep.name for ep in eps]})"
    )
