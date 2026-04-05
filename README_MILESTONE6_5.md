
# OpenMimicry Milestone 6.5

This bundle upgrades the old static 2D pack system into a character-based animated runtime.

## Included
- character-centric folder structure
- per-character `character.toml`
- state/animation folders with frame sequences
- playback modes:
  - `noloop`
  - `loopinfinity`
  - `loopduringtime`
  - `loopwhiletalk`
- optional PNG talk bubble
- default white bubble fallback
- input field and send button
- minimal structured backend/avatar JSON response
- local free TTS adapter using `pyttsx3`
- validation script
- two demo characters

## Suggested Make targets

```makefile
character-demo:
	OPENMIMICRY_PROFILE=$(PROFILE) .venv/bin/python scripts/run_character_demo.py --character-root characters/$(CHARACTER)

validate-character:
	OPENMIMICRY_PROFILE=$(PROFILE) .venv/bin/python scripts/validate_character.py --character-root characters/$(CHARACTER)
```

## Example commands

```bash
python scripts/validate_character.py --character-root characters/octomimic
python scripts/validate_character.py --character-root characters/mimic_blue

python scripts/run_character_demo.py --character-root characters/octomimic --provider ollama
python scripts/run_character_demo.py --character-root characters/mimic_blue --provider mock
```
