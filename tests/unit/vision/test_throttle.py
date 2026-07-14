"""Throttle + debouncer tests — pure logic, deterministic clock."""

from __future__ import annotations

from openmimicry.vision.pipeline import Debouncer, Throttle


def test_throttle_first_call_always_allows() -> None:
    now = [0]
    t = Throttle(target_fps=10, now_ms=lambda: now[0])
    assert t.allow() is True


def test_throttle_blocks_until_interval_elapsed() -> None:
    now = [0]
    t = Throttle(target_fps=10, now_ms=lambda: now[0])
    assert t.allow() is True
    now[0] = 50
    assert t.allow() is False
    now[0] = 100
    assert t.allow() is True
    now[0] = 199
    assert t.allow() is False
    now[0] = 200
    assert t.allow() is True


def test_throttle_interval_floor_is_one_ms() -> None:
    t = Throttle(target_fps=10_000, now_ms=lambda: 0)
    assert t.interval_ms >= 1


def test_debouncer_first_call_passes() -> None:
    now = [0]
    d = Debouncer(cooldown_ms=400, now_ms=lambda: now[0])
    assert d.allow("wave") is True


def test_debouncer_ignores_rapid_duplicates() -> None:
    now = [0]
    d = Debouncer(cooldown_ms=400, now_ms=lambda: now[0])
    assert d.allow("wave") is True
    now[0] = 100
    assert d.allow("wave") is False
    now[0] = 350
    assert d.allow("wave") is False
    now[0] = 401
    assert d.allow("wave") is True


def test_debouncer_per_key() -> None:
    now = [0]
    d = Debouncer(cooldown_ms=400, now_ms=lambda: now[0])
    assert d.allow("wave") is True
    assert d.allow("peace") is True
    assert d.allow("wave") is False
    assert d.allow("peace") is False


def test_debouncer_reset() -> None:
    now = [0]
    d = Debouncer(cooldown_ms=400, now_ms=lambda: now[0])
    d.allow("wave")
    d.reset("wave")
    assert d.allow("wave") is True
    d.allow("wave")
    d.reset()
    assert d.allow("wave") is True


def test_debouncer_drops_empty_key() -> None:
    d = Debouncer(cooldown_ms=400, now_ms=lambda: 0)
    assert d.allow("") is False
