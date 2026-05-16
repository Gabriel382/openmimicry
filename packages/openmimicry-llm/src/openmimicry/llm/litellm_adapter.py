"""``LiteLLMAdapter`` — wraps ``litellm.acompletion(..., stream=True)``.

LiteLLM is imported **lazily** inside ``generate()`` and ``healthcheck()``
so users who only need ``MockLLMAdapter`` (tests, CI, sandboxes without a
provider) don't have to install it. The constructor accepts a single
config-shaped dict to keep wiring small at the call sites.

Error mapping:

* connection / timeout / 5xx / rate-limit → :class:`LLMTransportError`
* 401 / 403 / "AuthenticationError" → :class:`LLMAuthError`
* anything else inheriting from ``Exception`` → :class:`LLMTransportError`
  (best-effort retryable; the router will decide whether to fall back).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from openmimicry.core.schemas import LLMChunk, LLMMessage, LLMUsage, ToolSpec

from .errors import LLMAuthError, LLMError, LLMTransportError

__all__ = [
    "LiteLLMAdapter",
    "LiteLLMSettings",
    "make_litellm_adapter",
]


FinishReason = Literal["stop", "length", "tool_calls", "content_filter"]
_ALLOWED_FINISH_REASONS: set[str] = {"stop", "length", "tool_calls", "content_filter"}


@dataclass(frozen=True)
class LiteLLMSettings:
    """Adapter-level configuration. Mirrors ``LLMConfig`` 1:1 but is a plain
    dataclass so the adapter has no Pydantic dependency at import time."""

    model: str = "openrouter/anthropic/claude-3.5-sonnet"
    temperature: float | None = None
    max_tokens: int | None = None
    api_base: str | None = None
    api_key_env: str | None = None
    request_timeout_s: int = 60
    extra: dict[str, Any] = field(default_factory=dict)


class LiteLLMAdapter:
    """An :class:`openmimicry.core.contracts.LLMAdapter` backed by LiteLLM.

    Construct with either explicit kwargs or a :class:`LiteLLMSettings`::

        LiteLLMAdapter(model="ollama/llama3.1")
        LiteLLMAdapter(settings=LiteLLMSettings(model="...", temperature=0.2))
    """

    name: str = "litellm"

    def __init__(
        self,
        model: str | None = None,
        *,
        settings: LiteLLMSettings | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        api_base: str | None = None,
        api_key_env: str | None = None,
        request_timeout_s: int | None = None,
    ) -> None:
        if settings is None:
            settings = LiteLLMSettings(
                model=model or "openrouter/anthropic/claude-3.5-sonnet",
                temperature=temperature,
                max_tokens=max_tokens,
                api_base=api_base,
                api_key_env=api_key_env,
                request_timeout_s=request_timeout_s if request_timeout_s is not None else 60,
            )
        elif model is not None:
            # An explicit `model` argument overrides whatever's in `settings`.
            settings = LiteLLMSettings(
                model=model,
                temperature=settings.temperature if temperature is None else temperature,
                max_tokens=settings.max_tokens if max_tokens is None else max_tokens,
                api_base=settings.api_base if api_base is None else api_base,
                api_key_env=settings.api_key_env if api_key_env is None else api_key_env,
                request_timeout_s=(
                    settings.request_timeout_s if request_timeout_s is None else request_timeout_s
                ),
                extra=dict(settings.extra),
            )
        self._settings = settings
        self._closed: bool = False

    # ------------------------------------------------------------------ API

    def generate(  # type: ignore[override]
        self,
        messages: Sequence[LLMMessage],
        *,
        stream: bool = True,
        tools: Sequence[ToolSpec] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        return self._stream(
            messages=list(messages),
            stream=stream,
            tools=list(tools) if tools else [],
            temperature=temperature if temperature is not None else self._settings.temperature,
            max_tokens=max_tokens if max_tokens is not None else self._settings.max_tokens,
        )

    async def _stream(
        self,
        *,
        messages: list[LLMMessage],
        stream: bool,
        tools: list[ToolSpec],
        temperature: float | None,
        max_tokens: int | None,
    ) -> AsyncIterator[LLMChunk]:
        if self._closed:
            raise LLMTransportError("LiteLLMAdapter is closed")

        litellm = _import_litellm()

        kwargs: dict[str, Any] = {
            "model": self._settings.model,
            "messages": [_to_litellm_message(m) for m in messages],
            "stream": stream,
            "timeout": self._settings.request_timeout_s,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if self._settings.api_base:
            kwargs["api_base"] = self._settings.api_base
        if self._settings.api_key_env:
            key = os.environ.get(self._settings.api_key_env)
            if not key:
                raise LLMAuthError(
                    f"environment variable {self._settings.api_key_env!r} is not set "
                    f"(required by api_key_env config for model {self._settings.model!r})"
                )
            kwargs["api_key"] = key
        if tools:
            kwargs["tools"] = [_to_litellm_tool(t) for t in tools]
        if self._settings.extra:
            kwargs.update(self._settings.extra)

        try:
            response = await litellm.acompletion(**kwargs)
        except Exception as exc:
            raise _classify_litellm_exception(exc) from exc

        if not stream:
            # Non-streaming: response is a single completion object.
            yield _completion_to_chunk(response, terminal=True)
            return

        try:
            async for raw_chunk in response:
                chunk = _streaming_chunk_to_llm_chunk(raw_chunk)
                if chunk is None:
                    continue
                yield chunk
        except LLMError:
            raise
        except Exception as exc:
            raise _classify_litellm_exception(exc) from exc

    async def healthcheck(self) -> bool:
        """Best-effort: succeeds iff LiteLLM is importable.

        We deliberately do not make a network call here — that's a job for
        ``/health`` in M6, which can decide to issue a cheap ping per
        configured model.
        """
        try:
            _import_litellm()
        except LLMTransportError:
            return False
        return not self._closed

    async def close(self) -> None:
        self._closed = True


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _import_litellm() -> Any:
    """Lazy-import ``litellm`` and raise a typed error on failure."""
    try:
        import litellm  # type: ignore[import-not-found]
    except ImportError as exc:
        raise LLMTransportError(
            'litellm is not installed. Install with `pip install "openmimicry-llm[litellm]"`.'
        ) from exc
    return litellm


def _to_litellm_message(msg: LLMMessage) -> dict[str, Any]:
    """Translate an ``LLMMessage`` to LiteLLM's dict shape."""
    out: dict[str, Any] = {"role": msg.role, "content": msg.content}
    if msg.name is not None:
        out["name"] = msg.name
    if msg.tool_call_id is not None:
        out["tool_call_id"] = msg.tool_call_id
    return out


def _to_litellm_tool(spec: ToolSpec) -> dict[str, Any]:
    """Translate a ``ToolSpec`` to LiteLLM's OpenAI-style tool dict."""
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.parameters,
        },
    }


def _streaming_chunk_to_llm_chunk(raw: Any) -> LLMChunk | None:
    """Translate one LiteLLM streaming chunk into an :class:`LLMChunk`.

    Returns ``None`` for chunks that contain no useful information (heartbeats
    that come from some providers).
    """
    try:
        choice = raw.choices[0]
    except (AttributeError, IndexError):
        return None

    delta_obj = getattr(choice, "delta", None) or getattr(choice, "message", None)
    delta_text: str = ""
    tool_calls: list[dict[str, Any]] = []

    if delta_obj is not None:
        delta_text = getattr(delta_obj, "content", None) or ""
        raw_tool_calls = getattr(delta_obj, "tool_calls", None) or []
        for tc in raw_tool_calls:
            tool_calls.append(_tool_call_to_dict(tc))

    finish_reason = _coerce_finish_reason(getattr(choice, "finish_reason", None))

    usage_obj = getattr(raw, "usage", None)
    usage = _usage_from_litellm(usage_obj) if usage_obj is not None else None

    if not delta_text and not tool_calls and finish_reason is None and usage is None:
        # Nothing to emit.
        return None

    return LLMChunk(
        delta=delta_text,
        finish_reason=finish_reason,
        tool_calls=tool_calls,
        usage=usage,
    )


def _completion_to_chunk(response: Any, *, terminal: bool) -> LLMChunk:
    """Translate a non-streaming LiteLLM completion into a single chunk."""
    fallback_finish_reason: FinishReason | None = "stop" if terminal else None

    try:
        choice = response.choices[0]
    except (AttributeError, IndexError):
        return LLMChunk(delta="", finish_reason=fallback_finish_reason)

    message_obj = getattr(choice, "message", None)
    delta_text = getattr(message_obj, "content", "") or "" if message_obj else ""
    tool_calls: list[dict[str, Any]] = []

    if message_obj is not None:
        for tc in getattr(message_obj, "tool_calls", None) or []:
            tool_calls.append(_tool_call_to_dict(tc))

    finish_reason = _coerce_finish_reason(getattr(choice, "finish_reason", None))
    usage = _usage_from_litellm(getattr(response, "usage", None))

    return LLMChunk(
        delta=delta_text,
        finish_reason=finish_reason or fallback_finish_reason,
        tool_calls=tool_calls,
        usage=usage,
    )


def _tool_call_to_dict(tc: Any) -> dict[str, Any]:
    """Best-effort translation of LiteLLM's tool-call object into a dict."""
    if isinstance(tc, dict):
        return tc

    out: dict[str, Any] = {}
    for key in ("id", "type"):
        val = getattr(tc, key, None)
        if val is not None:
            out[key] = val

    func = getattr(tc, "function", None)
    if func is not None:
        out["function"] = {
            "name": getattr(func, "name", None),
            "arguments": getattr(func, "arguments", None),
        }
    return out


def _coerce_finish_reason(raw: object) -> FinishReason | None:
    """Constrain LiteLLM's finish_reason to the contract's Literal set.

    Unknown provider-specific finish reasons are mapped to ``"stop"`` to
    preserve the previous runtime behavior while satisfying the typed schema.
    """
    if raw is None:
        return None
    if isinstance(raw, str) and raw in _ALLOWED_FINISH_REASONS:
        return cast(FinishReason, raw)
    return "stop"


def _usage_from_litellm(usage_obj: Any) -> LLMUsage | None:
    if usage_obj is None:
        return None
    try:
        return LLMUsage(
            prompt_tokens=int(getattr(usage_obj, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage_obj, "completion_tokens", 0) or 0),
            total_tokens=int(getattr(usage_obj, "total_tokens", 0) or 0),
        )
    except (TypeError, ValueError):
        return None


def _classify_litellm_exception(exc: BaseException) -> LLMError:
    """Map a LiteLLM exception to one of our typed errors."""
    name = type(exc).__name__
    msg = str(exc) or name
    if any(s in name for s in ("Auth", "PermissionDenied", "ForbiddenError")):
        return LLMAuthError(msg)
    if "401" in msg or "403" in msg or "API key" in msg or "api_key" in msg:
        return LLMAuthError(msg)
    return LLMTransportError(msg)


def make_litellm_adapter() -> LiteLLMAdapter:
    """Entry-point factory for the contract conftest.

    Returns an adapter pointed at a local Ollama model so the contract test
    can do a Protocol check without making a network call. The actual call
    is skipped at test time because LiteLLM may not be installed.
    """
    return LiteLLMAdapter(model="ollama/llama3.1")
