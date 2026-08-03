# OpenMimicry v1.4.0 release notes

v1.4.0 makes voice conversation deterministic and turns the browser dashboard
into the control point for recognition quality, model provider, and character
installation.

## Highlights

- Accepted turns are serialized; delayed answers cannot overtake later input.
- The last four completed interactions provide bounded LLM memory.
- Every recognized wake-listen phrase is visible, but missing-name and
  duplicate transcripts are explicitly marked and excluded from the LLM.
- RealtimeSTT is prewarmed with Accurate `small.en` by default, PTT finalizes
  on release, and configurable wake aliases recover common name errors.
- RealtimeTTS reuses one engine on a dedicated worker and gates visible text on
  actual playback start, fixing silent second/subsequent replies.
- The dashboard shows and switches between OpenRouter
  `openai/gpt-4o-mini` and local Ollama `gpt-oss:20b` presets.
- Sprite2D characters can be installed from validated ZIP files.

## Compatibility

Configuration schema remains version 1. Existing single-backend `llm.adapter`
and `llm.model` files continue to work. Named `llm.backends` are additive.
Existing character folders are unchanged; ZIP import is an additional install
path. No API keys are stored or returned by dashboard endpoints.

## Validation

- 538 Python tests passed.
- 92 desktop/frontend tests passed.
- Ruff, Pyright, import-boundary checks, config validation, pack validation,
  dashboard JavaScript syntax, and the production frontend build passed.

See `docs/V1.4.0_WINDOWS_TESTING.md` for the Windows acceptance run and
`docs/character_packs.md` for the import format.
