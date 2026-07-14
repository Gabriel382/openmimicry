# Configuration

OpenMimicry runtime behavior is configured by `config/app.yaml` plus an optional
profile. Non-secret desktop appearance is configured separately in
`config/theme.yml`, and assistant tone/cue vocabulary in
`config/personality.yml`.

## 1. Resolution order

1. Defaults baked into the schema (`openmimicry.core.schemas.app.AppConfig`).
2. The active config file. Looked up in this order:
   - `--config` CLI flag.
   - `OPENMIMICRY_CONFIG` environment variable.
   - `./config/app.yaml`.
   - `~/.config/openmimicry/app.yaml`.
3. A profile file, if `OPENMIMICRY_PROFILE` is set: `./config/profiles/<name>.yaml`, merged over the active file.
4. Environment variables of the form `OPENMIMICRY__<SECTION>__<KEY>=...`, applied last.

The merge is deep for nested dicts and replacement for scalars/lists. The final tree is validated; on failure, the process exits with a structured error pointing at the offending path.

## 2. Top-level schema

```yaml
schema_version: 1

app:
  log_level: INFO              # DEBUG | INFO | WARNING | ERROR
  log_format: json             # json | text
  data_dir: ~/.openmimicry
  telemetry: false             # off by default; never on without explicit opt-in

llm:
  adapter: litellm             # litellm | mock | <custom>
  model: openrouter/anthropic/claude-3.5-sonnet
  temperature: 0.7
  max_tokens: null
  api_base: null               # for self-hosted/OpenAI-compatible endpoints
  api_key_env: OPENROUTER_API_KEY
  request_timeout_s: 60
  retry:
    attempts: 2
    backoff_s: 1.5
  fallback:
    adapter: litellm
    model: ollama/llama3.1

voice:
  stt:
    adapter: realtimestt        # realtimestt | mock | <custom>
    language: en
    vad: silero                 # silero | webrtc | none
    sample_rate: 16000
    wake:
      enabled: true
      names: ["Mimi", "Hey Mimi"]
      sensitivity: 0.6
  tts:
    adapter: realtimetts        # realtimetts | mock | <custom>
    engine: coqui               # coqui | piper | azure | openai | ...
    voice: en_female_1
    rate: 1.0
    interruptible: true
  modes:
    text_always_on: true
    push_to_talk_hotkey: "Ctrl+Space"
    live_wake: true
    agent_voice: true
    barge_in_grace_ms: 600

avatar:
  runtime: sprite2d            # sprite2d | advanced2d | threejs | vrm | live3d | unity | external | mock
  pack: octomimic
  pack_roots:
    - ./characters
    - ~/.openmimicry/characters
  default_state: idle
  default_emotion: neutral
  transition_ms: 120
  celebration_ms: 1200
  error_ms: 1000
  runtimes:
    sprite2d:
      fit_to_character: false
    threejs:
      scene_background: transparent
      camera: { fov: 35, position: [0, 1.6, 1.4] }
      lighting: studio
      load: ~/.openmimicry/characters/octomimic.vrm   # or .glb / .gltf
    live3d:
      mouth_driver: amplitude          # amplitude | viseme
      gaze_driver: text                # text | webcam | none
      procedural_idle: true
      blend_window_ms: 250
    unity:
      transport: ws                    # ws | http | tcp | pipe
      endpoint: ws://127.0.0.1:7777
      reconnect: true
      directive_topic: avatar.directive
    external:
      transport: ws
      endpoint: ws://127.0.0.1:9000
      schema_version: 1

tasks:
  default_runtime: mcp_agent
  runtimes:
    mcp_agent:
      adapter: mcp_agent
      servers:
        - name: filesystem
          command: ["uvx", "mcp-server-filesystem", "~/projects"]
    claude_code:
      adapter: claude_code
      cli: claude
      working_dir: ~/projects
    local_shell:
      adapter: local_shell
      allowlist:
        - cmd: ls
          flags: ["-la", "-h"]
        - cmd: rg
          flags: ["--max-count", "--type"]
      working_dir: ~/projects
      audit_log: ~/.openmimicry/shell-audit.log

ui:
  overlay:
    width: 360
    height: 360
    fit_to_character: false
    interactive_padding_px: 40
    click_through_default: true
    always_on_top: true
    save_position: true
  panel:
    width: 480
    height: 720
    open_on_startup: false
  tray:
    enabled: true
  hotkeys:
    toggle_interact: "Ctrl+Shift+M"
    show_panel: "Ctrl+Shift+O"
```

Every section maps 1:1 to a Pydantic model in `openmimicry.core.schemas.app`. Models are frozen; the runtime gets read-only views.

## 3. Environment overrides

Double-underscore separates levels:

```bash
export OPENMIMICRY__LLM__MODEL=openrouter/anthropic/claude-3.5-haiku
export OPENMIMICRY__VOICE__MODES__AGENT_VOICE=false
export OPENMIMICRY__UI__OVERLAY__CLICK_THROUGH_DEFAULT=false
```

Booleans accept `true/false/1/0/yes/no`; lists accept JSON syntax (`'["a","b"]'`).

Secret values (API keys) are *not* in the YAML. They are referenced by env var name via `api_key_env: OPENROUTER_API_KEY`, and the adapter reads the env var at startup. Mistakes (env var missing) are surfaced on `/health`.

## 4. Hot reload

Some changes are safe to apply without restarting:

| Section | Hot-reload? |
|---|---|
| `app.log_level` | yes |
| `llm.temperature`, `max_tokens`, `model` (same adapter) | yes |
| `voice.modes.*` toggles | yes |
| `avatar.pack`, `avatar.transition_ms` | yes |
| `avatar.runtime` swap | yes (handled by `AvatarOrchestrator.swap_runtime`) |
| `avatar.runtimes.<modality>.*` | yes |
| `ui.*` toggles | yes (via Tauri commands) |
| `llm.adapter`, `voice.*.adapter`, `tasks.runtimes.*.adapter` | **no** (restart required) |
| `tasks.runtimes.*` add/remove | **no** |

`make doctor` and the panel's "Settings" page mark adapter-level changes as "needs restart".

The reloader watches the active config file with `watchfiles`, re-merges env overrides, re-validates, and `EventBus.publish(ConfigUpdated(diff))`. Each module decides whether the diff requires action.

## 5. Schema versioning

`schema_version: 1` is mandatory. Future major bumps:

- v2 might split `voice.tts` into engine-specific subtrees.
- v2 might add a `personalities` section.

Each bump ships with a migration function in `openmimicry.core.config.migrations` and the runtime refuses to load an older version unless `--allow-config-migrate` is passed.

## 6. Profiles

`config/profiles/` ships these working examples. Each profile is a small overlay
merged on top of `config/app.yaml`; choosing one is, for example,
`OPENMIMICRY_PROFILE=openrouter-voice make backend`.

- `basic.yaml` — Sprite2D with mock LLM, voice, and tasks; no key/network/audio.
- `openrouter-voice.yaml` — OpenRouter through LiteLLM, local RealtimeSTT, and
  operating-system TTS.
- `vision.yaml` — mocks plus the opt-in MediaPipe vision demonstration.

The install profile and `OPENMIMICRY_PROFILE` must use the same name when
optional dependencies are involved.

## 7. Appearance and personality files

`config/theme.yml` is validated by the backend and exposed through the
non-secret `GET /appearance` endpoint. Restart after editing it. Set
`OPENMIMICRY_APPEARANCE_PATH` to keep a personal theme elsewhere.

`config/personality.yml` defines the system prompt plus allow-listed emotions
and actions for structured avatar cues. Override its location with
`OPENMIMICRY_PERSONALITY_PATH`. Neither file may contain provider secrets.

## 8. Validation in CI

`scripts/validate_config.py` loads every YAML in `config/` and runs the validator. CI runs that script on every PR. Pack manifests are validated the same way via `scripts/validate_pack.py`. A PR that breaks the example configs cannot be merged.
