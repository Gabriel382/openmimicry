"""Structured assistant reply parsing with a safe plain-text fallback."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "ParsedAssistantReply",
    "PersonalitySettings",
    "load_personality",
    "parse_assistant_reply",
]


DEFAULT_EMOTIONS = (
    "neutral",
    "happy",
    "sad",
    "angry",
    "confused",
    "focused",
    "worried",
)
DEFAULT_ACTIONS = ("idle", "wave", "nod", "celebrate", "think", "none")


@dataclass(frozen=True)
class PersonalitySettings:
    system_prompt: str
    structured_avatar_output: bool
    allowed_emotions: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    cue_duration_ms: int


@dataclass(frozen=True)
class ParsedAssistantReply:
    text: str
    emotion: str = "neutral"
    action: str = "idle"
    intensity: float = 0.6
    duration_ms: int = 1800
    structured: bool = False


def load_personality(path: str | os.PathLike[str] | None = None) -> PersonalitySettings:
    raw_path = path or os.environ.get("OPENMIMICRY_PERSONALITY_PATH") or "config/personality.yml"
    candidate = Path(raw_path).expanduser()
    data: dict[str, Any] = {}
    if candidate.is_file():
        try:
            loaded = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            data = {}

    behaviour = data.get("behavior")
    if not isinstance(behaviour, dict):
        behaviour = {}
    emotions = _string_tuple(behaviour.get("allowed_emotions"), DEFAULT_EMOTIONS)
    actions = _string_tuple(behaviour.get("allowed_actions"), DEFAULT_ACTIONS)
    duration = _bounded_int(behaviour.get("cue_duration_ms"), 1800, 250, 15000)
    structured = bool(behaviour.get("structured_avatar_output", True))
    base_prompt = str(data.get("system_prompt") or "You are OpenMimicry, a helpful companion.")

    if structured:
        contract = (
            "\n\nReturn exactly one JSON object with this shape: "
            '{"reply":"your answer","emotion":"one allowed emotion",'
            '"action":"one allowed action","intensity":0.0}. '
            f"Allowed emotions: {', '.join(emotions)}. "
            f"Allowed actions: {', '.join(actions)}. "
            "Do not wrap the JSON in Markdown and do not add other keys."
        )
        base_prompt += contract

    return PersonalitySettings(
        system_prompt=base_prompt,
        structured_avatar_output=structured,
        allowed_emotions=emotions,
        allowed_actions=actions,
        cue_duration_ms=duration,
    )


def parse_assistant_reply(raw: str, settings: PersonalitySettings) -> ParsedAssistantReply:
    """Parse the JSON envelope; never expose malformed JSON to the user."""

    cleaned = raw.strip()
    if not cleaned:
        return ParsedAssistantReply(text="", duration_ms=settings.cue_duration_ms)
    if not settings.structured_avatar_output:
        return ParsedAssistantReply(text=cleaned, duration_ms=settings.cue_duration_ms)

    candidate = _strip_code_fence(cleaned)
    try:
        payload = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return ParsedAssistantReply(text=cleaned, duration_ms=settings.cue_duration_ms)
    if not isinstance(payload, dict):
        return ParsedAssistantReply(text=cleaned, duration_ms=settings.cue_duration_ms)

    reply = payload.get("reply", payload.get("text", payload.get("message")))
    if not isinstance(reply, str) or not reply.strip():
        return ParsedAssistantReply(text=cleaned, duration_ms=settings.cue_duration_ms)

    emotion = str(payload.get("emotion") or "neutral").strip().lower()
    if emotion not in settings.allowed_emotions:
        emotion = "neutral"
    action = str(payload.get("action") or "idle").strip().lower()
    if action not in settings.allowed_actions:
        action = "idle"
    try:
        intensity = float(payload.get("intensity", 0.6))
    except (TypeError, ValueError):
        intensity = 0.6

    return ParsedAssistantReply(
        text=reply.strip(),
        emotion=emotion,
        action=action,
        intensity=max(0.0, min(1.0, intensity)),
        duration_ms=settings.cue_duration_ms,
        structured=True,
    )


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _string_tuple(value: Any, fallback: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(value, list):
        return fallback
    cleaned = tuple(str(item).strip().lower() for item in value if str(item).strip())
    return cleaned or fallback


def _bounded_int(value: Any, fallback: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, parsed))
