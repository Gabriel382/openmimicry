"""``detect_task_intent(text) -> TaskRequest | None``.

Regex-first task-intent detection. If the user said something like "Ask
Claude to refactor utils.py" the function returns a :class:`TaskRequest`
with ``preferred_runtime`` set to the matched adapter; otherwise it
returns ``None`` so the caller falls back to normal LLM chat.

The matchers are intentionally permissive. False positives are fine —
the router can refuse if no adapter satisfies the capabilities. False
negatives are fine too — chat is the default.
"""

from __future__ import annotations

import re

from openmimicry.core.schemas.tasks import TaskRequest

__all__ = ["detect_task_intent"]


# Each tuple: (regex, preferred_runtime, capabilities_required).
_PATTERNS: list[tuple[re.Pattern[str], str, set[str]]] = [
    (
        re.compile(
            r"\b(?:ask|tell)\s+claude(?:\s+code)?\s+to\s+(?P<instr>.+)$",
            re.IGNORECASE | re.DOTALL,
        ),
        "claude_code",
        {"code"},
    ),
    (
        re.compile(
            r"\bsend\s+(?:this|that|it)\s+to\s+claude(?:\s+code)?\s*[:,.\s]\s*(?P<instr>.+)$",
            re.IGNORECASE | re.DOTALL,
        ),
        "claude_code",
        {"code"},
    ),
    (
        re.compile(
            r"\b(?:ask|use)\s+(?:the\s+)?mcp\s+agent\s+to\s+(?P<instr>.+)$",
            re.IGNORECASE | re.DOTALL,
        ),
        "mcp_agent",
        {"mcp"},
    ),
    (
        re.compile(
            r"\b(?:run|use)\s+(?:the\s+)?(?:local\s+)?shell\s+(?:to\s+)?(?P<instr>.+)$",
            re.IGNORECASE | re.DOTALL,
        ),
        "local_shell",
        {"shell"},
    ),
]


def detect_task_intent(text: str) -> TaskRequest | None:
    """Return a TaskRequest if ``text`` looks like a delegation; else None."""
    if not text or not text.strip():
        return None
    for pattern, runtime, caps in _PATTERNS:
        m = pattern.search(text)
        if m is None:
            continue
        instr = m.group("instr").strip().rstrip(".?!")
        if not instr:
            continue
        summary = _summarise(instr)
        return TaskRequest(
            summary=summary,
            instructions=instr,
            preferred_runtime=runtime,
            capabilities_required=set(caps),
        )
    return None


def _summarise(instr: str) -> str:
    """One-line summary suitable for ``TaskRequest.summary`` and bus events."""
    head = instr.strip().splitlines()[0]
    return head if len(head) <= 80 else head[:77] + "..."
