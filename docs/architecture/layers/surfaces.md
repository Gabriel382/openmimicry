# Layer: Surfaces

How OpenMimicry is **presented and assembled**. Surfaces own the
transports (HTTP, WebSocket), the UI shells (Tauri, browser, Unity),
and — uniquely — the *one file in the repository* where concrete
adapter classes are imported by name.

## Deployables

| App | What it is | Why it's a surface |
|-----|------------|--------------------|
| [`apps/backend`](../../../apps/backend/) | FastAPI service + WebSocket transport + `wiring.py` | The HTTP/WS edge of the system + the single assembly point. |
| [`apps/desktop/frontend`](../../../apps/desktop/frontend/) | Vite + React UI: speech bubble, top toolbar, runtime registry | Renders state, sends events. No business logic. |
| [`apps/desktop/src-tauri`](../../../apps/desktop/src-tauri/) | Tauri 2 shell: transparent avatar, docked toolbar, tray, global hotkeys | The native chrome around the frontend. |
| [`apps/unity-bridge`](../../../apps/unity-bridge/) | Unity ↔ FastAPI bridge for the Unity avatar runtime | A surface for a non-web renderer. |
| [`apps/external-echo`](../../../apps/external-echo/) | Reference external avatar — echoes directives to stdout/HTTP | Demonstrates the `External` runtime modality. |

## The `wiring.py` rule

The contract layer says concrete adapters live in their respective
packages. The surface layer says *concrete adapters are imported in
exactly one file*:

```
apps/backend/src/openmimicry_backend/wiring.py
```

That file reads `AppConfig`, picks the concrete adapter class for
each Protocol, instantiates it, and hands the dependency graph to
the FastAPI app. Every other module — including the tests — receives
its collaborators via constructor injection.

This is why a new contributor can grep `from openmimicry.llm.litellm`
and find every line that touches LiteLLM in the entire backend: one.

## Frontend rule: dumb where possible

The React frontend is intentionally a thin view:

- It connects to `/ws`, receives `AvatarDirective` events, and sends
  user-input events.
- It mounts one of five runtime components (Sprite2D, Three.js,
  Live3D, Unity, External) based on the current directive's
  `runtime_id`.
- It does not own a state machine. The director on the backend is
  the source of truth.

## Tauri rule: chrome, not logic

The Tauri shell owns: window positioning, transparency, click-through
toggling, global hotkeys (PTT), tray menu, and bootstrap of the
embedded webview. It does **not** own avatar logic, voice logic, or
LLM logic. Every Tauri ↔ frontend event uses the `namespace:event`
naming convention (Tauri 2.x rejects dots in event names).

## Develop a surface in isolation

```bash
# Backend only (no frontend, no Tauri) — uses MockLLM + MockSTT/TTS
make backend

# Frontend only (no Tauri) — connects to a running backend via Vite proxy
make frontend

# Tauri shell — pulls frontend via beforeDevCommand, also needs backend
make desktop

# external-echo — no GUI, just a Python script tailing directives
python apps/external-echo/main.py --backend http://localhost:8000
```

## Adding a new surface

A new surface is usually one of three things:

1. **A new UI shell** (e.g. an Electron build, a CLI repl). Connect
   to the existing `/ws` and `/chat` HTTP API. No `wiring.py`
   changes.
2. **A new transport** (e.g. a gRPC face on the same runtime).
   Subscribe to the `EventBus` and forward events. The Runtime
   container's `lifespan` already supports multiple subscribers.
3. **A new external renderer** (e.g. an OBS plugin). Implement the
   External runtime contract — see `apps/external-echo` as the
   reference.

Surfaces are the cheapest layer to add because they don't change
contracts. If your "new surface" wants to add a field to
`AvatarDirective`, that's actually a contract change — go through
`docs/contracts.md` §11 first.
