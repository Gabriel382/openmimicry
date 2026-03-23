
# Emotion + speaking patch

This patch updates the animated 2D runtime so that:
- the runtime prefers `<emotion>_speaking` folders whenever the reply contains text
- if `<emotion>_speaking` is missing, it falls back to `speaking`
- if `speaking` is missing, it falls back to the base emotion animation
- TTS and emotion now happen at the same time through the selected speaking variant

## New runtime rule

- no reply text -> play `emotion`
- reply text -> try `emotion_speaking`
- fallback -> `speaking`
- fallback -> `emotion`

## Example commands

```bash
python scripts/validate_character.py --character-root characters/octomimic
python scripts/run_character_demo.py --character-root characters/octomimic --provider ollama
```
