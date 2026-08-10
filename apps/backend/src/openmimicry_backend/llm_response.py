"""Structured assistant reply parsing with a safe plain-text fallback."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "ParsedAssistantReply",
    "PersonalitySettings",
    "load_personality",
    "parse_assistant_reply",
    "speech_safe_text",
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
_BUILTIN_PERSONALITY = Path("config/personality.yml")
_LOCAL_PERSONALITY = Path("~/.openmimicry/personality.yml")


@dataclass(frozen=True)
class PersonalitySettings:
    system_prompt: str
    structured_avatar_output: bool
    allowed_emotions: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    cue_duration_ms: int
    assistant_name: str = "OpenMimicry"
    assistant_aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedAssistantReply:
    text: str
    emotion: str = "neutral"
    action: str = "idle"
    intensity: float = 0.6
    duration_ms: int = 1800
    structured: bool = False


def load_personality(
    path: str | os.PathLike[str] | None = None,
    *,
    output_language: str = "en",
) -> PersonalitySettings:
    configured = path or os.environ.get("OPENMIMICRY_PERSONALITY_PATH")
    if configured is not None:
        candidate = Path(configured).expanduser()
    else:
        local = _LOCAL_PERSONALITY.expanduser()
        candidate = local if local.is_file() else _BUILTIN_PERSONALITY
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
    assistant_name = str(data.get("assistant_name") or "OpenMimicry").strip() or "OpenMimicry"
    assistant_aliases = _string_tuple(data.get("aliases"), ())

    language_names = {
        "en": "English",
        "fr": "French",
        "es": "Spanish",
        "pt": "Brazilian Portuguese",
        "pt-BR": "Brazilian Portuguese",
    }
    identity_contract = (
        f"\n\nYour assistant name is {assistant_name}. "
        "Facts named user_name or legacy name in memory describe the USER, never you. "
        "Never introduce yourself using a user's remembered name."
    )
    if assistant_aliases:
        identity_contract += " Your accepted aliases are: " + ", ".join(assistant_aliases) + "."
    language_name = language_names.get(output_language)
    if language_name:
        identity_contract += f" Reply in {language_name} unless the user explicitly asks otherwise."
    elif output_language == "auto":
        identity_contract += " Reply in the language used by the user's latest message."
    base_prompt += identity_contract

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
        assistant_name=assistant_name,
        assistant_aliases=assistant_aliases,
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
    embedded_prefix = ""
    if not candidate.startswith("{"):
        embedded = _last_reply_object(candidate)
        if embedded is not None:
            embedded_prefix, candidate = embedded
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

    # Models occasionally emit the answer and then repeat it inside the JSON
    # envelope. The structured reply is authoritative; do not expose or speak
    # the duplicate prefix. If the prefix contains different prose, it is also
    # omitted because the frozen envelope is the only validated output.
    _ = embedded_prefix
    return ParsedAssistantReply(
        text=reply.strip(),
        emotion=emotion,
        action=action,
        intensity=max(0.0, min(1.0, intensity)),
        duration_ms=settings.cue_duration_ms,
        structured=True,
    )


_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(https?://[^)]+\)")
_SOURCE_LINE_RE = re.compile(r"(?im)^\s*(?:sources?|references?|citations?)\s*:\s*.*(?:\n|$)")
_INLINE_CITATION_RE = re.compile(r"\s*\[(?:\d+(?:\s*,\s*\d+)*)\]")


def speech_safe_text(text: str) -> str:
    """Return a natural TTS rendering without reading URLs/citation syntax.

    The full answer remains available in text history. Only the spoken copy is
    simplified, which keeps optional web attribution accessible without making
    the companion recite links aloud.
    """

    value = _MARKDOWN_LINK_RE.sub(r"\1", text)
    value = _SOURCE_LINE_RE.sub("", value)
    value = _URL_RE.sub("", value)
    value = _INLINE_CITATION_RE.sub("", value)
    return " ".join(value.split()).strip()


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _last_reply_object(text: str) -> tuple[str, str] | None:
    """Find a trailing JSON reply object after accidental plain text."""

    decoder = json.JSONDecoder()
    for index in range(len(text) - 1, -1, -1):
        if text[index] != "{":
            continue
        try:
            payload, consumed = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or not any(
            key in payload for key in ("reply", "text", "message")
        ):
            continue
        if text[index + consumed :].strip():
            continue
        return text[:index].strip(), text[index : index + consumed]
    return None


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
