from __future__ import annotations

from openmimicry_backend.llm_response import (
    PersonalitySettings,
    parse_assistant_reply,
)


def _settings() -> PersonalitySettings:
    return PersonalitySettings(
        system_prompt="test",
        structured_avatar_output=True,
        allowed_emotions=("neutral", "happy"),
        allowed_actions=("idle", "wave"),
        cue_duration_ms=1800,
    )


def test_parses_structured_reply_and_avatar_cue() -> None:
    parsed = parse_assistant_reply(
        '{"reply":"Hello","emotion":"happy","action":"wave","intensity":0.8}',
        _settings(),
    )
    assert parsed.text == "Hello"
    assert parsed.emotion == "happy"
    assert parsed.action == "wave"
    assert parsed.intensity == 0.8
    assert parsed.structured is True


def test_invalid_cue_values_fall_back_to_allow_list_defaults() -> None:
    parsed = parse_assistant_reply(
        '{"reply":"Safe","emotion":"malicious","action":"delete","intensity":99}',
        _settings(),
    )
    assert parsed.emotion == "neutral"
    assert parsed.action == "idle"
    assert parsed.intensity == 1.0


def test_plain_text_is_preserved_when_model_ignores_json_contract() -> None:
    parsed = parse_assistant_reply("A normal answer", _settings())
    assert parsed.text == "A normal answer"
    assert parsed.structured is False
