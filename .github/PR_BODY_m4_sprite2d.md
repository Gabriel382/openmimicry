# feat(avatar): M4 — Sprite2DAvatarAdapter + frontend runtime

Lands the first concrete `AvatarRuntimeAdapter` per `docs/modules/M4_avatar_sprite2d.md`. M3's substrate (director, orchestrator, pack loader) was the prereq; M6 will eventually supply the real WS bridge but the adapter is fully testable today with a `FakeBridge`.

## Python side

- **`openmimicry.avatar.runtimes.sprite2d.projection.build_sprite2d_projection(directive, pack)`** — produces the `avatar.directive` wire message from `docs/contracts.md` §9:
  ```json
  {
    "type": "avatar.directive",
    "runtime": "sprite2d",
    "directive": { /* AvatarDirective */ },
    "frames": ["/static/characters/<id>/states/idle/0.png", ...],
    "fps": 10,
    "loop": true
  }
  ```
  Honours every §4–§6 rule:
  - Speaking + present `speaking_frames` → speaking frames; otherwise fall back to base.
  - Unknown `state` → fall back to `pack.default_state`.
  - File paths are rebased onto a configurable URL prefix (default `/static/characters`).
- **`openmimicry.avatar.runtimes.sprite2d.adapter.Sprite2DAvatarAdapter`** — the adapter itself.
  - `__init__(*, pack=None, ws_bridge=None, static_url_prefix="/static/characters")`. Tests pass a `FakeBridge`; M6 will pass the live WS handle.
  - `apply_directive(d)` builds the projection and publishes it. Never raises on missing pack / unknown state / unsupported fields (`gesture`, `gaze`, `intensity`). Warns once per unknown state.
  - `set_text` → `bubble.text`; `start_speaking` / `stop_speaking` / `set_visibility` → corresponding wire messages.
  - `load_character(id, config)` loads a pack from `config["pack_path"]` (or `characters/<id>` default) and auto-emits a fresh idle directive.
  - Registered via `openmimicry.contracts.avatar_runtime` (`sprite2d` key).
- **`WSBridge`** — minimal `Protocol` with `async publish(msg: dict)`. M6 implements it.

## Frontend side

- **`apps/desktop/frontend/src/runtimes/sprite2d/Sprite2DRuntime.tsx`** — React component. Renders the first frame on mount, advances via `setInterval(1000/fps)`, wraps on `loop=true`, clamps on `loop=false`, resets to frame 0 on a new frame set. Emits debug `data-state` / `data-frame-idx` attrs.
- **`preloader.ts`** — caches `HTMLImageElement`s by URL; `preload(frames)` resolves once every image has loaded; tolerates load errors via an `onError` hook (resolves the promise anyway so the renderer can show partial frames).
- **`index.ts`** — barrel exports.
- **`apps/desktop/frontend/src/runtimes/registry.ts`** — first entry: `{ sprite2d: Sprite2DRuntime }`. Future modalities (Three.js, Live3D, Unity, External) add themselves here.

## Tests

**Python:**

- `tests/unit/avatar/runtimes/test_sprite2d_projection.py` — projection shape, speaking-frames fallback, unknown-state fallback to default, `loop=false` for `happy`, URL rewriting against `pack_id`, custom prefix.
- `tests/unit/avatar/runtimes/test_sprite2d_adapter.py` — `FakeBridge` records messages; projection is the published payload; ignores unsupported directive fields without raising; warns ONCE per unknown state; survives `bridge.publish` errors; `set_text` / `start_speaking` / `stop_speaking` / `set_visibility` shapes; `load_character` swaps the pack and emits a fresh idle directive; healthcheck + idempotent shutdown.
- `tests/contract/test_avatar_runtime.py` — hermetic guard widened so `sprite2d` participates alongside `mock`; the entry-point factory uses a null bridge so the protocol checks stay offline.

**Frontend (Vitest + jsdom):**

- `__tests__/preloader.test.ts` — caches every URL after preload; second preload with overlapping URLs reuses the cached `HTMLImageElement`; `onError` hook fires when an image fails.
- `__tests__/Sprite2DRuntime.test.tsx` — first frame on mount; fake-timer advance at the configured fps; `loop=true` wraps; `loop=false` clamps at last frame; frame-set change resets to frame 0; empty-projection renders an empty wrapper.

## Definition-of-done checklist

- [x] `Sprite2DAvatarAdapter` registered via entry point; passes the contract test.
- [x] Frontend `Sprite2DRuntime` renders frames at the configured fps (Vitest fake timers prove it).
- [x] Unknown `state` falls back to `pack.default_state`; logs a warning **once**.
- [x] `apply_directive` with `speaking=True` uses `speaking_frames` when present, else falls back to base.
- [x] `apply_directive` ignores `gesture` / `gaze` / `intensity` without raising.
- [x] Preloader caches frame URLs (test reuses the cached image on second preload).
- [x] `scripts/check_imports.py` clean — `openmimicry-avatar` still depends only on `openmimicry-core`.
- [x] `CHANGELOG.md` entry added; README updated with the wiring example.
- [ ] Manual smoke: the two shipped packs (`octomimic`, `mimic_blue`) render in the dev frontend (M7 wiring required).

The last item is "manual smoke" because M6 / M7 hasn't landed yet — the Python tests prove the projection shape and the adapter's bridge calls, and the frontend tests prove the renderer behaves correctly given a projection. Once M7 mounts the runtime and M6 connects the bus to a WS, the full path is live.

## Files

```
packages/openmimicry-avatar/
  pyproject.toml                                                       [+ sprite2d entry point]
  README.md                                                            [+ wiring example]
  src/openmimicry/avatar/__init__.py                                   [+ Sprite2DAvatarAdapter export]
  src/openmimicry/avatar/runtimes/__init__.py                          [+ Sprite2DAvatarAdapter re-export]
  src/openmimicry/avatar/runtimes/sprite2d/
    __init__.py
    projection.py                                                      [build_sprite2d_projection]
    adapter.py                                                         [Sprite2DAvatarAdapter, WSBridge]
tests/unit/avatar/runtimes/
  __init__.py
  test_sprite2d_projection.py
  test_sprite2d_adapter.py
tests/contract/test_avatar_runtime.py                                  [hermetic guard widened]
apps/desktop/frontend/src/runtimes/
  registry.ts                                                          [sprite2d -> Sprite2DRuntime]
  sprite2d/
    Sprite2DRuntime.tsx
    preloader.ts
    index.ts
    __tests__/Sprite2DRuntime.test.tsx
    __tests__/preloader.test.ts
CHANGELOG.md                                                           [M4 entry]
```

## Labels

`module:avatar`, `m4`
