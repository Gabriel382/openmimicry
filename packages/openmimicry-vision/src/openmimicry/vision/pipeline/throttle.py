"""Throttle + debounce helpers — pure logic, no GPU.

* :class:`Throttle` honours ``target_fps`` by computing whether enough
  wall-clock time has elapsed since the last accepted frame.
* :class:`Debouncer` ignores rapid duplicates of the same gesture
  name (``"wave"`` fired five times per second is one wave, not
  five).

Both helpers take a pluggable ``now`` so unit tests can drive them
without sleeping.
"""

from __future__ import annotations

from collections.abc import Callable

__all__ = ["Debouncer", "Throttle"]


def _default_now_ms() -> int:
    import time

    return int(time.monotonic() * 1000)


class Throttle:
    """Rate limiter keyed by wall clock.

    ``allow()`` returns ``True`` at most once every
    ``1000 / target_fps`` milliseconds. The first call always
    succeeds, so consumers don't have to special-case startup.
    """

    def __init__(
        self,
        target_fps: int,
        *,
        now_ms: Callable[[], int] | None = None,
    ) -> None:
        self._interval_ms: int = max(1, 1000 // max(1, target_fps))
        self._now_ms = now_ms or _default_now_ms
        self._last_ms: int = -10_000_000

    @property
    def interval_ms(self) -> int:
        return self._interval_ms

    def allow(self) -> bool:
        t = self._now_ms()
        if t - self._last_ms < self._interval_ms:
            return False
        self._last_ms = t
        return True

    def reset(self) -> None:
        self._last_ms = -10_000_000


class Debouncer:
    """Per-key debounce.

    Use it to suppress repeated firings of the same gesture name. A
    detection passes through only when it differs from the last
    accepted name OR ``cooldown_ms`` has elapsed since the previous
    accepted firing of the same name.
    """

    def __init__(
        self,
        cooldown_ms: int = 600,
        *,
        now_ms: Callable[[], int] | None = None,
    ) -> None:
        self._cooldown_ms = max(0, cooldown_ms)
        self._now_ms = now_ms or _default_now_ms
        self._last_seen: dict[str, int] = {}

    @property
    def cooldown_ms(self) -> int:
        return self._cooldown_ms

    def allow(self, key: str) -> bool:
        if not key:
            return False
        t = self._now_ms()
        last = self._last_seen.get(key, -10_000_000)
        if t - last < self._cooldown_ms:
            return False
        self._last_seen[key] = t
        return True

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._last_seen.clear()
        else:
            self._last_seen.pop(key, None)
