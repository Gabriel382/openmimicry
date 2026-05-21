#!/usr/bin/env python3
"""M1 smoke demo -- streams chunks from an LLMAdapter to stdout.

Use cases (one command, zero scaffolding):

* No setup -- exercises ``MockLLMAdapter`` (the canonical fixture):

      python scripts/m1_demo.py

* Local Ollama -- requires `ollama serve` running and a model pulled:

      python scripts/m1_demo.py --model ollama/llama3.1 --prompt "Say hi"

* Cloud provider via LiteLLM -- requires the key in env:

      export OPENROUTER_API_KEY=sk-...
      python scripts/m1_demo.py \
          --model openrouter/anthropic/claude-3.5-sonnet \
          --api-key-env OPENROUTER_API_KEY \
          --prompt "Two-sentence haiku about modular code."

* Router with fallback -- primary degrades to fallback on transport error:

      python scripts/m1_demo.py --model openrouter/... \
          --fallback ollama/llama3.1 \
          --prompt "Explain CRDTs in 30 words."

Exit code 0 on success, 1 on a typed LLM error so CI/Make can `&&` it.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence

from openmimicry.core.schemas import LLMMessage
from openmimicry.llm import (
    LiteLLMAdapter,
    LLMAuthError,
    LLMRouter,
    LLMTransportError,
    MockLLMAdapter,
)
from openmimicry.llm.prompts import load as load_prompt


def _build_adapter(args: argparse.Namespace):
    """Return either a MockLLMAdapter or a LiteLLMAdapter (+ optional router)."""
    if args.model == "mock":
        return MockLLMAdapter(script=args.script or None)

    primary = LiteLLMAdapter(
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        api_key_env=args.api_key_env,
        api_base=args.api_base,
    )

    if args.fallback:
        fallback = LiteLLMAdapter(model=args.fallback, api_key_env=args.api_key_env)
        return LLMRouter(primary=primary, fallback=fallback)
    return primary


def _build_messages(args: argparse.Namespace) -> list[LLMMessage]:
    system = (
        load_prompt(
            "system_personality",
            name=args.persona_name,
            style=args.persona_style,
            language=args.persona_language,
        )
        if args.persona_style
        else load_prompt("system_default")
    )
    return [
        LLMMessage(role="system", content=system.strip()),
        LLMMessage(role="user", content=args.prompt),
    ]


async def _run(args: argparse.Namespace) -> int:
    adapter = _build_adapter(args)
    messages = _build_messages(args)

    print(f"--- {getattr(adapter, 'name', '?')} -> {args.model} ---", file=sys.stderr)
    try:
        async for chunk in adapter.generate(
            messages,
            stream=not args.no_stream,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        ):
            if chunk.delta:
                sys.stdout.write(chunk.delta)
                sys.stdout.flush()
            if chunk.finish_reason is not None:
                sys.stdout.write("\n")
                if chunk.usage and not args.quiet:
                    print(
                        f"[usage] prompt={chunk.usage.prompt_tokens} "
                        f"completion={chunk.usage.completion_tokens} "
                        f"total={chunk.usage.total_tokens}",
                        file=sys.stderr,
                    )
    except LLMAuthError as exc:
        print(f"[auth] {exc}", file=sys.stderr)
        return 1
    except LLMTransportError as exc:
        print(f"[transport] {exc}", file=sys.stderr)
        return 1
    finally:
        await adapter.close()

    return 0


def _parse(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="OpenMimicry M1 smoke demo")
    p.add_argument(
        "--model",
        default="mock",
        help="LiteLLM model id (e.g. ollama/llama3.1, openrouter/anthropic/claude-3.5-sonnet). "
        "Use 'mock' (default) for the in-process scripted adapter.",
    )
    p.add_argument(
        "--fallback",
        default=None,
        help="Optional fallback model id. Wraps both behind LLMRouter.",
    )
    p.add_argument(
        "--api-key-env",
        default=None,
        help="Env var holding the provider API key (e.g. OPENROUTER_API_KEY).",
    )
    p.add_argument("--api-base", default=None, help="Custom API base URL (self-hosted endpoints).")
    p.add_argument("--prompt", default="Say hello in one short sentence.")
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--max-tokens", type=int, default=None)
    p.add_argument("--no-stream", action="store_true", help="Disable streaming.")
    p.add_argument("--quiet", action="store_true", help="Suppress usage line on stderr.")
    p.add_argument(
        "--script",
        nargs="+",
        default=None,
        help="When --model=mock, override the script (space-separated deltas).",
    )
    # Persona controls (route through the prompt registry).
    p.add_argument("--persona-name", default="Mimi")
    p.add_argument(
        "--persona-style",
        default=None,
        help="If set, use system_personality.j2; otherwise system_default.txt.",
    )
    p.add_argument("--persona-language", default="English")
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
