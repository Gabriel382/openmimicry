"""Tiny prompt registry -- .txt and .j2 templates packaged as data files.

The default templates ship under this directory. load(prompt_name, **vars)
resolves prompt_name to <prompt_name>.txt or <prompt_name>.j2 in this
folder (in that order), reads it, and either returns its contents
verbatim (.txt) or renders it with Jinja2 (.j2).

prompt_name is positional-only so callers can pass name=... as a template
variable without colliding with the lookup key.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

__all__ = ["PromptNotFoundError", "PromptRegistry", "load"]


_PACKAGE_DIR = Path(__file__).resolve().parent


class PromptNotFoundError(KeyError):
    """Raised when load(prompt_name) cannot find <prompt_name>.txt|.j2."""


class PromptRegistry:
    """Resolves prompt names against an ordered list of search paths."""

    def __init__(self, search_paths: Iterable[Path | str] | None = None) -> None:
        self._search_paths: list[Path] = [_PACKAGE_DIR]
        if search_paths:
            for p in search_paths:
                self.add_search_path(p)

    def add_search_path(self, path: Path | str) -> None:
        """Prepend path so user-supplied prompts win over defaults."""
        resolved = Path(path).resolve()
        if not resolved.is_dir():
            raise FileNotFoundError(f"prompt search path not a directory: {resolved}")
        self._search_paths.insert(0, resolved)

    def render(self, prompt_name: str, /, **variables: Any) -> str:
        """Resolve and render prompt_name."""
        for base in self._search_paths:
            txt = base / f"{prompt_name}.txt"
            if txt.is_file():
                return txt.read_text(encoding="utf-8")
            j2 = base / f"{prompt_name}.j2"
            if j2.is_file():
                env = Environment(
                    loader=FileSystemLoader(str(base)),
                    undefined=StrictUndefined,
                    autoescape=False,
                    keep_trailing_newline=True,
                )
                try:
                    template = env.get_template(f"{prompt_name}.j2")
                except TemplateNotFound as exc:  # pragma: no cover
                    raise PromptNotFoundError(prompt_name) from exc
                return template.render(**variables)
        raise PromptNotFoundError(prompt_name)


_DEFAULT_REGISTRY = PromptRegistry()


def load(prompt_name: str, /, **variables: Any) -> str:
    """Module-level convenience for the default registry."""
    return _DEFAULT_REGISTRY.render(prompt_name, **variables)
