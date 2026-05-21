# Module M6: `apps/backend`

## Goal (1 line)

Wire the five package contracts into a running FastAPI process: an HTTP `/chat`, a WebSocket projection to the frontend, a `/health` endpoint, and the `wiring.py` that assembles concrete adapters from `AppConfig`.

## Scope and non-scope

**In scope.**

- The FastAPI process at `apps/backend/`.
- `wiring.py` — the **only** file that imports concrete adapters from `packages/openmimicry-llm`, `packages/openmimicry-voice`, `packages/openmimicry-avatar`, `packages/openmimicry-tasks`. Everything else uses Protocols.
- WebSocket projection: subscribes to the `EventBus`, transforms `RuntimeEvent`s into the frontend wire-protocol messages from `contracts.md` §9.
- HTTP endpoints: `POST /chat`, `GET /health`, `POST /mode/toggle`, `POST /pack/swap`, `POST /runtime/swap`, `GET /config`, `POST /admin/reload`.
- Intent classification call-out (uses `openmimicry.tasks.intent`) on user text submissions.
- Graceful shutdown wired to `Runtime.stop()`.

**Non-scope.**

- Any business logic. M6 imports and assembles; it does not invent.
- The frontend (M7).
- The Tauri shell (M8).

## Inputs (immutable, from contracts.md)

- Every Protocol from `contracts.md` §3–§6.
- Every schema from `contracts.md` §2 + §7.
- Frontend wire protocol from `contracts.md` §9 — M6 is the producer of inbound projection messages and the consumer of outbound user-input messages.

## Outputs (this module owns)

```text
apps/backend/
  pyproject.toml
  README.md
  src/openmimicry_backend/
    __init__.py
    main.py                 # uvicorn entrypoint, FastAPI app
    wiring.py               # build_runtime(config) -> Runtime
    ws.py                   # WebSocket projection (subscribe + send)
    routes/
      __init__.py
      chat.py               # /chat POST
      health.py             # /health GET
      mode.py               # /mode/toggle POST
      pack.py               # /pack/swap, /runtime/swap
      admin.py              # /admin/reload, /config GET (debug-gated)
    projection.py           # RuntimeEvent -> wire protocol mapper
tests/integration/backend/
  test_chat_flow.py
  test_ptt_flow.py
  test_wake_flow.py
  test_task_flow.py
  test_ws_projection.py
  test_health.py
```

## Mock implementations this module provides

None — M6 is an application, not a library. It does provide test fixtures:

- `tests/fixtures/configs/integration.yaml` — a minimal config using only mocks.
- `tests/integration/backend/conftest.py::client` — a FastAPI `TestClient` plus an open WebSocket connection.

## Test surface

- **Integration.** `test_chat_flow.py`: POST `/chat` with `{ "text": "Hi" }`. Assert the WebSocket receives in order: `avatar.directive` thinking, `bubble.text` partial × N, `avatar.directive` speaking, `bubble.text` complete, `avatar.directive` idle.
- **Integration.** `test_ptt_flow.py`: send `{"type":"ptt.down"}`, drive `MockSTTAdapter.push_transcript("hi", is_final=True)`, send `{"type":"ptt.up"}`. Assert the same downstream flow as above.
- **Integration.** `test_wake_flow.py`: enable live wake, push a transcript starting with "Mimi". Assert `WakeDetected` is published and the chat flow runs.
- **Integration.** `test_task_flow.py`: send `{"text":"Ask Claude to summarise readme"}`. Intent classifier routes to `MockTaskRuntimeAdapter`. Assert `task.card` updates arrive on the WS.
- **Integration.** `test_ws_projection.py`: every `RuntimeEvent` type is checked for its WS projection (or correctly suppressed).
- **Integration.** `test_health.py`: with a healthy mock LLM, `/health` returns `{ "ok": true, "adapters": {...} }`. With a stubbed unhealthy mock, `ok: false`.

## Step-by-step plan (atomic, numbered)

1. Create `apps/backend/pyproject.toml`. Path deps on `openmimicry-core`, `openmimicry-llm`, `openmimicry-voice`, `openmimicry-avatar`, `openmimicry-tasks`. Runtime dep `fastapi`, `uvicorn[standard]`, `websockets`.
2. Implement `wiring.py::build_runtime(config: AppConfig, bus: EventBus) -> Runtime`. For each adapter family, look up `config.<family>.adapter`, import the matching concrete class (LiteLLM/Realtime*/MCPAgent/Sprite2D/…) or its Mock counterpart when `adapter: mock`. Pure dispatch — no logic.
3. Implement `projection.py::project(event: RuntimeEvent) -> dict | None`. The exhaustive mapping from `contracts.md` §9. Returns `None` for events that don't project (e.g. raw `LLMTokenStreamed` is folded into `bubble.text`).
4. Implement `ws.py`. On WebSocket connect: spawn a coroutine subscribing to `EventBus`, project each event, and `await websocket.send_json(msg)`. On inbound message: `user.text` → `Runtime.handle_user_text(text)`; `ptt.down`/`ptt.up` → `SpeechController.ptt_down/up`; `mode.toggle` → update `ConfigUpdated` on the bus and the runtime.
5. Implement `main.py`. FastAPI app, lifespan that builds the `Runtime`, mounts routes, mounts the WS at `/ws`. Static-files mount at `/static/characters/` serving the configured `avatar.pack_roots`.
6. Implement `/chat`: schema `{ text: str }`. Runs intent classifier; if no intent, falls back to LLM. Returns 202 immediately and lets the WS deliver progress.
7. Implement `/health`. Awaits `adapter.healthcheck()` on every wired adapter with a short timeout each. Returns `{ ok, adapters: {...}, version, schema_version }`.
8. Implement `/mode/toggle`. Body `{ key: "live_wake"|"agent_voice", value: bool }`. Publishes `ConfigUpdated` and calls the matching `SpeechController` method.
9. Implement `/pack/swap` and `/runtime/swap`. Body `{ pack: str }` or `{ runtime: "sprite2d"|"threejs"|... }`. Calls `AvatarOrchestrator.load_character` or `.swap_runtime`.
10. Implement `/admin/reload`. Re-runs the config loader, publishes `ConfigUpdated`.
11. Write the integration tests using `httpx.AsyncClient` and the FastAPI `TestClient`'s WS support. Use `MockLLMAdapter`, `MockSTTAdapter`, `MockTTSAdapter`, `MockTaskRuntimeAdapter`, `Sprite2DAvatarAdapter` (with a fake bridge).
12. Add `apps/backend/README.md` with a 20-line "run it" snippet.
13. Update `CHANGELOG.md`.
14. `make ci`. Open PR `feat(backend): M6 — FastAPI process, wiring, WebSocket projection`.

## Definition of done (checklist)

- [ ] `make backend` starts the server on `:8000`.
- [ ] `wiring.py` is the **only** file in the repository that imports a concrete adapter class.
- [ ] `GET /health` returns 200 with adapter status when all mocks are wired.
- [ ] Every integration test passes.
- [ ] WS projection mapping covers every `RuntimeEvent` variant from `contracts.md` §2.1.
- [ ] Intent classifier routes "Ask Claude to ..." to a task, not the LLM chat path.
- [ ] Graceful shutdown completes within 2s (`Runtime.stop()` awaited).
- [ ] `scripts/check_imports.py` clean — but note that `wiring.py` is on the allowlist.
- [ ] `CHANGELOG.md` entry.

## Recommended LLM brief (copy-pasteable prompt)

> You are implementing **Module M6 (`apps/backend`)** of OpenMimicry. M0–M5 have landed; every Protocol has at least a mock implementation, plus concrete adapters for LiteLLM, RealtimeSTT, RealtimeTTS, mcp-agent, Claude Code, and Sprite2D.
>
> Read in order:
>
> 1. `docs/contracts.md` — every Protocol and schema. `§9` is the WebSocket wire protocol you must produce and consume.
> 2. `docs/modules/M6_backend.md` — this brief.
> 3. `docs/architecture.md` §9–§11 — process topology, event flows.
> 4. `docs/event_flows.md` — the exact sequences your integration tests must reproduce.
>
> Implement the 14-step plan. Critical rule: **`wiring.py` is the only file in the repo that imports concrete adapter classes.** Every other file in `apps/backend/` uses Protocols from `openmimicry.core.contracts.*`. The CI step `scripts/check_imports.py` has an explicit allowlist for `apps/backend/src/openmimicry_backend/wiring.py`; do not bypass it elsewhere.
>
> The integration tests in `tests/integration/backend/` are the executable spec for end-to-end behaviour. Use the mock adapters from M1–M5 as their fixtures.
>
> Open the PR titled `feat(backend): M6 — FastAPI process, wiring, WebSocket projection` with the Definition-of-done checklist ticked.
