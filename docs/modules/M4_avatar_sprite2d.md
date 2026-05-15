# Module M4: `Sprite2DAvatarAdapter`

## Goal (1 line)

Ship the first concrete `AvatarRuntimeAdapter` — a 2D sprite/frame-sequence renderer that consumes `AvatarDirective`s in the backend and projects render-ready commands over the WebSocket so the frontend Sprite2D component can play the right frame folder.

## Scope and non-scope

**In scope.**

- `Sprite2DAvatarAdapter` (Python): the backend-side adapter that translates `AvatarDirective` into a `Sprite2DProjection` message and publishes it via the WebSocket transport.
- The frontend `Sprite2DRuntime` component (in `apps/desktop/frontend/src/runtimes/sprite2d/`) that consumes that message.
- A small frame-pre-loader on the frontend so transitions don't flash.
- The pack-resolution logic for `emotion + emotion_speaking` fallback (delegated to the loader from M3, but consumed here).
- Unit + contract tests against `MockAvatarRuntimeAdapter`-equivalents for the Python side; Vitest tests for the React component.

**Non-scope.**

- The `AvatarRuntimeAdapter` Protocol (Phase 0).
- The pack loader and director (M3).
- The frontend shell, overlay window, and WebSocket plumbing (M7, M8).
- Any 3D / VRM / Unity rendering (later modalities).

## Inputs (immutable, from contracts.md)

- `AvatarRuntimeAdapter` Protocol (`contracts.md` §5).
- `AvatarDirective`, `State`, `Emotion`, `CharacterPack`, `EmotionFrames` (`contracts.md` §2.3, §2.4).
- `Sprite2DProjection` wire-protocol message (subset of the avatar-directive frontend projection in `contracts.md` §9 plus the resolved frame paths). Defined here, registered as **Stable** in `contracts.md` §9 in this PR. The shape:
  ```json
  {
    "type": "avatar.directive",
    "runtime": "sprite2d",
    "directive": { /* AvatarDirective */ },
    "frames": ["frames/idle/0.png", "frames/idle/1.png", ...],
    "fps": 10,
    "loop": true
  }
  ```
- `AvatarConfig.runtimes.sprite2d` from [`../configuration.md`](../configuration.md).

## Outputs (this module owns)

Python:

```text
packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/sprite2d/
  __init__.py
  adapter.py              # Sprite2DAvatarAdapter
  projection.py           # build_sprite2d_projection(directive, pack) -> dict
tests/unit/avatar/runtimes/
  test_sprite2d_adapter.py
  test_sprite2d_projection.py
```

Frontend:

```text
apps/desktop/frontend/src/runtimes/sprite2d/
  Sprite2DRuntime.tsx     # React component
  preloader.ts            # frame-pre-loader
  index.ts                # exports
  __tests__/
    Sprite2DRuntime.test.tsx
    preloader.test.ts
```

Plus an entry in `apps/desktop/frontend/src/runtimes/registry.ts` mapping `"sprite2d"` → `Sprite2DRuntime`.

## Mock implementations this module provides

None. This *is* the concrete implementation. Other modules use `MockAvatarRuntimeAdapter` from M3 in their tests; M4's tests use the real `Sprite2DAvatarAdapter` against a `MockWebSocketBridge`.

## Test surface

- **Unit (Python).** `build_sprite2d_projection(directive, pack)`:
  - Maps `directive.state="thinking", speaking=False` → frames from `pack.emotions["thinking"].frames`.
  - Maps `directive.state="thinking", speaking=True` → frames from `.speaking_frames`, falling back to `.frames` if missing.
  - Honours `fps` and `loop` from the pack.
- **Unit (Python).** `Sprite2DAvatarAdapter.apply_directive(d)` calls the projection builder and publishes via the injected bridge.
- **Contract (Python).** `Sprite2DAvatarAdapter` passes `tests/contract/test_avatar_runtime.py` (registered via entry point so the contract conftest discovers it). Accepting `AvatarDirective` with `gesture`, `gaze`, `intensity` fields it doesn't use must not raise.
- **Unit (Frontend).** `Sprite2DRuntime` renders the first frame on mount, advances frames at the configured fps (use fake timers in Vitest), preloads the next frame folder on `apply_directive`.
- **Unit (Frontend).** Preloader does not re-fetch the same frame folder if already cached.

## Step-by-step plan (atomic, numbered)

1. Add the `Sprite2DProjection` wire shape to `docs/contracts.md` §9 (additive change; ship in a separate "contracts amendment" PR if §9 is already merged, or include directly if this is the first amendment).
2. Implement `projection.py::build_sprite2d_projection(directive, pack)`. Resolve frame paths to URL-relative paths (the frontend will fetch them via `/static/characters/<id>/...`).
3. Implement `adapter.py::Sprite2DAvatarAdapter`:
   - `__init__(self, pack: CharacterPack, ws_bridge)`. `ws_bridge` is an interface with `publish(msg: dict)` that M6 supplies.
   - `apply_directive(d)`: build the projection, await `ws_bridge.publish(...)`.
   - `set_text(text)`: publish `{ "type": "bubble.text", "text": text, "complete": True }`.
   - `start_speaking(text=None)`: publish a state transition with `speaking=True`.
   - `stop_speaking()`: publish with `speaking=False`.
   - `set_visibility(visible)`: publish `{ "type": "system.notice", "kind": "visibility", "visible": visible }`.
   - `load_character(id, config)`: validate the id exists, swap the active pack, send a fresh idle directive.
   - `shutdown()`: idempotent close.
4. Register `Sprite2DAvatarAdapter` via entry point `openmimicry.contracts.avatar_runtime`.
5. Implement frontend `Sprite2DRuntime.tsx`:
   - Props: `{ runtimeConfig }`. Subscribes to the WS message stream (provided via context — M7 owns the provider).
   - State: `{ frames: string[], fps: number, loop: boolean, currentIdx: number }`.
   - `useEffect` registers a handler for `avatar.directive` messages with `runtime === "sprite2d"`.
   - `setInterval(1000/fps)` advances `currentIdx`; `loop=false` clamps at the last frame.
   - Renders `<img src={frames[currentIdx]} className="avatar-frame" />`.
6. Implement `preloader.ts`. `preload(frames: string[])` returns a Promise that resolves when every `<img>.onload` fires; caches via a `Map<string, HTMLImageElement>`.
7. Add `apps/desktop/frontend/src/runtimes/registry.ts`. Initial entry: `{ sprite2d: Sprite2DRuntime }`. Future modalities add themselves here.
8. Write Vitest tests using `@testing-library/react`, `vi.useFakeTimers()`.
9. Write Python unit tests using a small `FakeBridge` that records `publish` calls.
10. Un-skip the contract test for `sprite2d` in `tests/contract/test_avatar_runtime.py`.
11. Add a short usage entry to `packages/openmimicry-avatar/README.md` showing Sprite2D wiring.
12. Update `CHANGELOG.md`.
13. `make ci`. Open PR `feat(avatar): M4 — Sprite2DAvatarAdapter + frontend runtime`.

## Definition of done (checklist)

- [ ] `Sprite2DAvatarAdapter` registered via entry point, passes the contract test.
- [ ] Frontend `Sprite2DRuntime` renders frames at the configured fps with Vitest fake timers proving it.
- [ ] `apply_directive` with an unknown `state` falls back to `pack.default_state`; logs a warning once.
- [ ] `apply_directive` with `speaking=True` uses `speaking_frames` when present, otherwise falls back to base frames.
- [ ] `apply_directive` ignores unsupported fields (`gesture`, `gaze`, `intensity`) without raising.
- [ ] Preloader caches frame URLs.
- [ ] The two shipped packs (`octomimic`, `mimic_blue`) render in a manual smoke test.
- [ ] `scripts/check_imports.py` clean.
- [ ] `CHANGELOG.md` entry.

## Recommended LLM brief (copy-pasteable prompt)

> You are implementing **Module M4 (`Sprite2DAvatarAdapter`)** of OpenMimicry. M3 (`openmimicry-avatar` core) has landed; the Protocol, schemas, pack loader, director, and orchestrator are stable.
>
> Read in order:
>
> 1. `docs/contracts.md` §2.3, §2.4, §5, §9 — `AvatarDirective`, `CharacterPack`, the Protocol, the wire-protocol projection.
> 2. `docs/modules/M4_avatar_sprite2d.md` — this brief.
> 3. `docs/character_packs.md` — frame folder convention, the `emotion + emotion_speaking` fallback rule you must honour.
> 4. `docs/avatar_modalities.md` §1.1 — what Sprite2D is and what fields it ignores by design.
> 5. `docs/desktop_overlay.md` §6 — how the frontend mount node is provisioned.
>
> Implement the 13-step plan. The adapter must accept any well-formed `AvatarDirective` (including fields it doesn't render) without raising. Ignore `gesture`, `gaze`, `intensity` — that is correct behaviour for Sprite2D.
>
> Two pieces of code live in two repos roots: Python at `packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/sprite2d/` and TypeScript at `apps/desktop/frontend/src/runtimes/sprite2d/`. They communicate exclusively via the wire protocol defined in `contracts.md` §9.
>
> Constraint: do not import from sibling Python packages other than `openmimicry-core` and your parent `openmimicry-avatar`. The frontend code goes in `apps/desktop/frontend/`; do not touch `apps/desktop/src-tauri` (M8's territory). Open the PR titled `feat(avatar): M4 — Sprite2DAvatarAdapter + frontend runtime` with the Definition-of-done checklist ticked.
