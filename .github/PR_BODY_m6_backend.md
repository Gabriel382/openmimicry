# feat(backend): M6 — FastAPI process, wiring, WebSocket projection

Implements `docs/modules/M6_backend.md` against the frozen contracts in
`docs/contracts.md`.

## What lands

### `apps/backend/`

```
apps/backend/
  pyproject.toml
  README.md
  src/openmimicry_backend/
    __init__.py
    main.py            # FastAPI app + lifespan + WS mount + uvicorn entry
    wiring.py          # the single concrete-adapter assembly point
    projection.py      # RuntimeEvent -> wire-protocol mapper
    ws.py              # BroadcastBridge + /ws endpoint
    routes/
      health.py        # GET /health
      chat.py          # POST /chat — intent-classified
      mode.py          # POST /mode/toggle
      pack.py          # POST /pack/swap, POST /runtime/swap
      admin.py         # GET /config (debug-gated), POST /admin/reload
```

### Critical rule enforced

`wiring.py` is the **only** file in the repository (besides `mocks.py`
files and the test tree) that imports concrete adapter classes. Every
route, the projector, the WS handler, and `main.py` read state via
Protocol-typed attributes on the assembled `Wiring` dataclass.
`scripts/check_imports.py` already exempts the wiring path. No other
backend file touches `openmimicry.{llm,voice,avatar,tasks}` directly.

### `Wiring` assembly

`build_runtime(config: AppConfig, *, ws_bridge=...) -> Wiring`:

- LLM: `mock` / `litellm` — `MockLLMAdapter` or `LiteLLMAdapter` with
  `LiteLLMSettings` populated from `config.llm`.
- Voice: `mock` / `realtimestt` / `realtimetts` plus a
  `SpeechController` over the chosen pair.
- Avatar: `mock` / `sprite2d`. The Sprite2D adapter receives the
  injected `ws_bridge`.
- Tasks: a `TaskRouter` keyed by `config.tasks.runtimes[*].adapter`;
  the per-name dispatch picks `mock` / `local_shell` / `claude_code` /
  `mcp_agent`. Default runtime falls open to the first registered
  adapter if the config names an unknown one.

`adapters_by_family` is surfaced on `Wiring` for `/health` introspection.

### WebSocket projection

`projection.project(event)` is the exhaustive mapping from
`RuntimeEvent` variants to the five wire shapes in `contracts.md` §9
(`transcript.preview`, `bubble.text`, `task.card`, `system.notice`).
State-transition events that the avatar runtime already emits as
`avatar.directive` (via the bridge) return `None` so the wire isn't
double-published. The mapping is unit-tested per-variant in
`tests/integration/backend/test_ws_projection.py`.

`BroadcastBridge` is a process-wide fan-out: every connected `/ws`
socket is registered with `add_socket`; `publish(message)` sends to all.
A dead socket is dropped on the first failed send so the broadcast
stays healthy. The Sprite2D adapter publishes `avatar.directive`
through this same bridge.

### Inbound WS

`user.text` -> `UserTextSubmitted` + `run_chat_turn(...)`.
`ptt.down` / `ptt.up` -> `SpeechController.ptt_down/up`.
`mode.toggle` -> `ConfigUpdated` + `enable/disable_live_listening` /
`interrupt`.

### `/chat` pipeline

```
text -> detect_task_intent
            |
   match? --|--> tasks.submit(req) -> stream updates onto bus -> TaskCompleted
   no   ----|--> LLMStarted -> [feed deltas to speech.say(generator)]
                              -> LLMTokenStreamed × N (per delta)
                              -> SpeechController publishes TTSStarted/TTSFinished
                              -> LLMReplyComplete
```

Returns `202 Accepted` immediately; delivery happens on the WS.

### Lifespan + shutdown

`main.lifespan` builds the `Wiring`, mounts `/static/characters` to the
first existing entry under `avatar.pack_roots` (skipped when nothing
exists, so tests with `pack_roots: []` don't bomb), starts the
controllers, and enforces a 2 s graceful shutdown budget covering
`orchestrator.stop()` + `speech.stop()` + `runtime.stop()`.

### `Makefile`

- `install-workspace` now also runs `pip install -e apps/backend`.
- New target `make backend-m6` runs `uvicorn
  openmimicry_backend.main:app`; the legacy `backend` target stays
  during the prototype-to-package migration.

### Lint / type / coverage

- `pyproject.toml` ruff `extend-exclude` now scoped to `apps/desktop`
  (Tauri shell) instead of the entire `apps/` tree.
- pyright `include` adds `apps/backend/src`; `exclude` keeps
  `apps/desktop`.
- `coverage.run.source` adds `apps/backend/src`.

### Tests

`tests/integration/backend/`:

- `test_health.py` — `/health` returns 200 with `ok: true` over the
  mock stack; flipping a mock's `healthcheck` flips `ok` to false.
- `test_chat_flow.py` — `POST /chat` returns 202; the bus sees
  `LLMTokenStreamed × N` then `LLMReplyComplete`; reconstructed
  full-text equals concatenated deltas.
- `test_task_flow.py` — `"Ask Claude to summarise readme"` triggers
  `TaskSubmitted` + `TaskCompleted` on the bus and emits **no**
  `LLMTokenStreamed`; every `TaskUpdatedEvent` references the
  submitted handle.
- `test_ptt_flow.py` — `speech.ptt_down()` publishes
  `UserSpeechStarted`; a final transcript pushed onto the mock STT
  followed by `ptt_up()` publishes `UserSpeechFinal` with the right
  text.
- `test_wake_flow.py` — `enable_live_listening` + pushed transcript
  -> `UserSpeechFinal` containing the wake name.
- `test_ws_projection.py` — every `RuntimeEvent` variant is asserted
  for its projected wire shape (or correctly suppressed).

`tests/fixtures/configs/integration.yaml` — mocks-only `AppConfig`
fixture for the suite.

## Out of scope (deferred)

- M7 (frontend) — the wire shapes are now stable and the React
  runtime can be wired up.
- M8 (Tauri shell) — separate brief.
- Full WS smoke through `TestClient.websocket_connect` is exercised
  manually; the integration tests inspect the bus directly to keep
  the suite hermetic and quick.

Closes the M6 task.
