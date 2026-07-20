"""Fast deterministic extraction plus an optional independent LLM pass."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Protocol

from .models import MemoryCandidate

__all__ = ["DeterministicExtractor", "LLMExtractor", "MemoryLLM"]


class MemoryLLM(Protocol):
    async def complete(self, prompt: str) -> str: ...


class DeterministicExtractor:
    """Extract only explicit first-person facts; never infer sensitive data."""

    _patterns: Sequence[tuple[str, re.Pattern[str]]] = (
        ("name", re.compile(r"\bmy name is\s+([^.!?]{1,80})", re.IGNORECASE)),
        ("location", re.compile(r"\bi (?:live|reside) in\s+([^.!?]{1,120})", re.IGNORECASE)),
        (
            "likes",
            re.compile(r"\bi (?:really )?(?:like|love|enjoy)\s+([^.!?]{1,180})", re.IGNORECASE),
        ),
        ("dislikes", re.compile(r"\bi (?:dislike|hate)\s+([^.!?]{1,180})", re.IGNORECASE)),
        ("preference", re.compile(r"\bi prefer\s+([^.!?]{1,180})", re.IGNORECASE)),
    )

    def extract(self, user_text: str, _assistant_text: str) -> list[MemoryCandidate]:
        candidates: list[MemoryCandidate] = []
        for predicate, pattern in self._patterns:
            for match in pattern.finditer(user_text):
                value = " ".join(match.group(1).strip(" ,;:\t\r\n").split())
                if value:
                    candidates.append(
                        MemoryCandidate(predicate=predicate, value=value, confidence=1.0)
                    )
        return candidates


class LLMExtractor:
    """Use a separately selected LLM and reject every non-schema result."""

    def __init__(self, llm: MemoryLLM) -> None:
        self._llm = llm

    async def extract(self, user_text: str, assistant_text: str) -> list[MemoryCandidate]:
        prompt = (
            "Extract only durable, explicitly stated user preferences or facts. "
            "Do not infer sensitive attributes. Return JSON only as "
            '{"memories":[{"predicate":"...","value":"...","confidence":0.0}]}. '
            f"User: {user_text}\nAssistant: {assistant_text}"
        )
        raw = await self._llm.complete(prompt)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []
        items = payload.get("memories", []) if isinstance(payload, dict) else []
        results: list[MemoryCandidate] = []
        for item in items[:12] if isinstance(items, list) else []:
            try:
                results.append(MemoryCandidate.model_validate(item))
            except Exception:
                continue
        return results
