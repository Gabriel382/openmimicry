"""Named, runtime-selectable LLM backends behind the frozen adapter contract."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence

from openmimicry.core.contracts import LLMAdapter
from openmimicry.core.schemas import LLMChunk, LLMMessage, ToolSpec

__all__ = ["LLMSwitchboard"]


class LLMSwitchboard:
    """Delegate each new generation to the currently selected backend."""

    name = "llm-switchboard"

    def __init__(
        self,
        *,
        backends: Mapping[str, LLMAdapter],
        models: Mapping[str, str],
        active: str,
    ) -> None:
        if not backends:
            raise ValueError("LLMSwitchboard requires at least one backend")
        if active not in backends:
            raise ValueError(f"unknown active LLM backend {active!r}")
        self._backends = dict(backends)
        self._models = dict(models)
        self._active = active

    @property
    def active_backend(self) -> str:
        return self._active

    @property
    def active_model(self) -> str:
        return self._models[self._active]

    @property
    def profiles(self) -> dict[str, dict[str, str]]:
        return {
            name: {
                "adapter": adapter.name,
                "model": self._models.get(name, "unknown"),
            }
            for name, adapter in self._backends.items()
        }

    def select(self, name: str) -> None:
        if name not in self._backends:
            raise ValueError(
                f"unknown LLM backend {name!r}; expected one of {sorted(self._backends)}"
            )
        self._active = name

    def backend(self, name: str | None = None) -> LLMAdapter:
        selected = name or self._active
        if selected not in self._backends:
            raise ValueError(f"unknown LLM backend {selected!r}")
        return self._backends[selected]

    def select_model(self, backend: str, model: str) -> None:
        if backend not in self._backends:
            raise ValueError(f"unknown LLM backend {backend!r}")
        selector = getattr(self._backends[backend], "select_model", None)
        if not callable(selector):
            raise ValueError(f"LLM backend {backend!r} does not support runtime model selection")
        selector(model)
        self._models[backend] = model

    def set_session_api_key(self, backend: str, value: str) -> None:
        if backend not in self._backends:
            raise ValueError(f"unknown LLM backend {backend!r}")
        setter = getattr(self._backends[backend], "set_session_api_key", None)
        if not callable(setter):
            raise ValueError(f"LLM backend {backend!r} does not accept API credentials")
        setter(value)

    def clear_session_api_key(self, backend: str) -> None:
        if backend not in self._backends:
            raise ValueError(f"unknown LLM backend {backend!r}")
        clearer = getattr(self._backends[backend], "clear_session_api_key", None)
        if callable(clearer):
            clearer()

    def credential_status(self, backend: str) -> dict[str, bool]:
        if backend not in self._backends:
            raise ValueError(f"unknown LLM backend {backend!r}")
        adapter = self._backends[backend]
        settings = getattr(adapter, "_settings", None)
        env_name = getattr(settings, "api_key_env", None)
        import os

        return {
            "session": bool(getattr(adapter, "has_session_api_key", False)),
            "environment": bool(env_name and os.environ.get(env_name)),
        }

    def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        stream: bool = True,
        tools: Sequence[ToolSpec] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        # Capture the adapter at turn start. A dashboard switch affects the
        # next turn and never splices two providers into one response.
        adapter = self._backends[self._active]
        return adapter.generate(
            messages,
            stream=stream,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def healthcheck(self) -> bool:
        return await self._backends[self._active].healthcheck()

    async def close(self) -> None:
        for adapter in self._backends.values():
            await adapter.close()
