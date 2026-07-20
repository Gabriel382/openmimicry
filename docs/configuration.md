# Configuration

OpenMimicry runtime behavior is configured by `config/app.yaml` plus an optional
profile. The browser dashboard stores non-secret user overrides such as the
wake name and end-of-speech pause in ignored `config/user.yaml`. Desktop appearance is configured in
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
4. The optional user overlay at `config/user.yaml`, or the path named by
   `OPENMIMICRY_USER_CONFIG`, merged over the profile.
5. Environment variables of the form `OPENMIMICRY__<SECTION>__<KEY>=...`,
   applied last.

The merge is deep for nested dicts and replacement for scalars/lists. The final tree is validated; on failure, the process exits with a structured error pointing at the offending path.

## 2. Top-level schema

```yaml
schema_version: 2

app:
  log_level: INFO              # DEBUG | INFO | WARNING | ERROR
  log_format: json             # json | text
  data_dir: ~/.openmimicry
  telemetry: false             # off by default; never on without explicit opt-in

llm:
  active_backend: openrouter
  history_turns: 4             # completed user/assistant pairs; 0–10
  backends:
    openrouter:
      adapter: litellm
      model: openrouter/openai/gpt-oss-20b
      api_key_env: OPENROUTER_API_KEY
      request_timeout_s: 90
    ollama:
      adapter: litellm
      model: ollama_chat/gpt-oss:20b
      api_base: http://127.0.0.1:11434
      api_key_env: null
      request_timeout_s: 180

voice:
  stt:
    adapter: isolated-faster-whisper  # supported default | mock | legacy realtimestt
    language: en
    model: medium.en            # CPU default; distil-large-v3 for NVIDIA
    realtime_model_type: medium.en  # legacy adapter compatibility only
    use_main_model_for_realtime: true
    device: auto                # auto | cpu | cuda
    compute_type: auto          # auto -> CPU int8 / CUDA float16
    beam_size: 5
    speech_threshold: 0.015     # live energy-VAD threshold
    vad: silero                 # silero | webrtc | none
    sample_rate: 16000
    post_speech_silence_duration: 1.0  # 0.2–3.0 s; raise if pauses cut speech
    wake:
      enabled: true
      names: ["Mimi", "Hey Mimi"]
      aliases: ["Me me"]
      sensitivity: 0.6
  tts:
    adapter: system-command     # mock | system-command | isolated-piper | chatterbox-local | elevenlabs
    engine: system
    voice: system-default
    data_dir: ~/.openmimicry/voices
    rate: 1.0
    interruptible: true
    readiness_timeout_s: 30     # up to 180 for cold-start clone models
  modes:
    text_always_on: true
    push_to_talk_hotkey: "Ctrl+Space"
    continuous_listening: false  # advanced: submit every final utterance
    live_wake: false             # toolbar: require configured name prefix
    agent_voice: true
    barge_in_enabled: false      # safe default for laptop speakers
    barge_in_grace_ms: 600

interaction:
  response_presentation:
    mode: parallel              # parallel | voice_ready | text_only | voice_only
    dismiss_policy: after_both
    minimum_ms: 2500
    base_ms: 1500
    ms_per_character: 55
    maximum_ms: 30000
    allow_accessibility_captions: true

memory:
  enabled: false                # no retention until explicitly enabled
  provider: none                # none | local | hindsight
  database_path: ~/.openmimicry/memory/memory.sqlite3
  endpoint: null                # required for enabled Hindsight
  retrieval_limit: 6
  retrieval_deadline_ms: 150
  retention_days: 365           # local SQLite; null means no automatic expiry
  extraction_mode: deterministic # deterministic | llm
  llm_backend: null             # independent named backend for LLM extraction
  store_raw_audio: false        # invariant; true is rejected

distribution:
  profile: commercial           # core | local | cloud | commercial | community
  reject_licenses: [GPL, AGPL, non-commercial, CC-BY-NC, research-only, unknown]

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
  tray:
    enabled: true
  hotkeys:
    toggle_interact: "Ctrl+Shift+M"
    show_panel: "Ctrl+Shift+O"  # legacy name; opens the browser dashboard
```

Every section maps 1:1 to a Pydantic model in `openmimicry.core.schemas.app`. Models are frozen; the runtime gets read-only views.

## 3. Environment overrides

Double-underscore separates levels:

```bash
export OPENMIMICRY__LLM__BACKENDS__OPENROUTER__MODEL=openrouter/anthropic/claude-3.5-haiku
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
| `voice.stt.post_speech_silence_duration` | yes (dashboard restarts active listener) |
| `voice.stt.model` | yes (dashboard warms and swaps the model) |
| `llm.active_backend` | yes (next accepted turn) |
| `avatar.pack`, `avatar.transition_ms` | yes |
| `avatar.runtime` swap | yes (handled by `AvatarOrchestrator.swap_runtime`) |
| `avatar.runtimes.<modality>.*` | yes |
| `ui.*` toggles | yes (via Tauri commands) |
| `llm.adapter`, `voice.*.adapter`, `tasks.runtimes.*.adapter` | **no** (restart required) |
| `tasks.runtimes.*` add/remove | **no** |

`make doctor` and the browser dashboard's Settings card mark adapter-level changes as "needs restart".

The reloader watches the active config file with `watchfiles`, re-merges env overrides, re-validates, and `EventBus.publish(ConfigUpdated(diff))`. Each module decides whether the diff requires action.

## 5. Schema versioning

`schema_version: 2` is current. The loader contains a deterministic v1→v2
migration for legacy single-LLM and voice configurations. The backend opts into
that migration in memory and never overwrites the source file. Library callers
remain strict unless they pass `allow_migrate=True`; a version newer than the
running code is always rejected.

## 6. Profiles

`config/profiles/` ships these working examples. Each profile is a small overlay
merged on top of `config/app.yaml`; choosing one is, for example,
`OPENMIMICRY_PROFILE=openrouter-voice make backend`.

- `basic.yaml` — Sprite2D with mock LLM, voice, and tasks; no key/network/audio.
- `openrouter-voice.yaml` — OpenRouter through LiteLLM, isolated local
  Faster-Whisper/Piper voice, plus a dashboard-selectable Ollama `gpt-oss:20b`
  backend. This is a community/GPL profile because current Piper is GPL-3.0.
- `openrouter-commercial.yaml` — OpenRouter/Ollama, isolated Faster-Whisper,
  and dependency-free operating-system TTS; no Piper installation.
- `openrouter-chatterbox.yaml` — free local Chatterbox voice cloning in a
  prewarmed disposable worker. Explicit consent and a reference recording are
  required; this is an opt-in community profile.
- `openrouter-elevenlabs.yaml` — remote BYOK voice selected in an ElevenLabs
  account. The API token remains in an environment variable or process memory.
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

`scripts/validate_config.py` validates `config/app.yaml` alone and merged with
every profile in `config/profiles/`. Appearance and personality schemas have
their own backend tests. Pack manifests are validated through
`scripts/validate_pack.py`. A PR that breaks a shipped example cannot be
merged.
