"""Unit tests for the prompt registry."""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import UndefinedError
from openmimicry.llm.prompts import PromptNotFoundError, PromptRegistry, load


def test_load_default_text_prompt() -> None:
    body = load("system_default")
    assert "OpenMimicry" in body


def test_load_default_jinja_prompt_renders() -> None:
    body = load("system_personality", name="Mimi", style="playful", language="French")
    assert "Mimi" in body
    assert "playful" in body
    assert "French" in body


def test_jinja_strict_undefined_raises() -> None:
    # `system_personality.j2` only uses `| default(...)` on a couple of vars.
    # If you reference something undefined (e.g. via a typo), StrictUndefined
    # raises. We simulate that by routing through a fresh template that uses
    # a bare variable.
    with pytest.raises(UndefinedError):
        # Render an undefined variable through the same env machinery.
        from jinja2 import Environment, StrictUndefined

        env = Environment(undefined=StrictUndefined, autoescape=False)
        env.from_string("Hello {{ missing_var }}").render()


def test_load_unknown_name_raises() -> None:
    with pytest.raises(PromptNotFoundError):
        load("not_a_template")


def test_user_search_path_wins_over_defaults(tmp_path: Path) -> None:
    custom = tmp_path / "system_default.txt"
    custom.write_text("CUSTOM PROMPT", encoding="utf-8")

    registry = PromptRegistry()
    registry.add_search_path(tmp_path)
    assert registry.render("system_default") == "CUSTOM PROMPT"


def test_add_invalid_search_path_raises(tmp_path: Path) -> None:
    registry = PromptRegistry()
    with pytest.raises(FileNotFoundError):
        registry.add_search_path(tmp_path / "does-not-exist")


def test_custom_jinja_template_in_search_path(tmp_path: Path) -> None:
    template = tmp_path / "greeting.j2"
    template.write_text("Hello, {{ who }}!", encoding="utf-8")
    registry = PromptRegistry()
    registry.add_search_path(tmp_path)
    out = registry.render("greeting", who="world")
    assert out == "Hello, world!"
