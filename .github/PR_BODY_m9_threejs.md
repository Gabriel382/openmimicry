# feat(avatar): M9 — ThreeJSAvatarAdapter + frontend Three.js runtime

Implements `docs/modules/M9_avatar_threejs.md`. Second concrete
`AvatarRuntimeAdapter` — proves the M3/M4 pluggability story.

## What lands

### Python — `ThreeJSAvatarAdapter`

```
packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/threejs/
  __init__.py
  adapter.py
  projection.py
```

- `build_threejs_projection(directive, pack)` — pure. Builds the
  additive §9 wire shape:
  ```json
  {
    "type": "avatar.directive",
    "runtime": "threejs",
    "directive": { ... },
    "asset": { "kind": "vrm" | "gltf", "url": "...", "pack_id": "..." },
    "clip": "happy_speaking",
    "fallbackClips": ["happy_speaking_speaking","happy_speaking","speaking","idle"],
    "blendWeights": { "talk": 0.88, "happy": 0.6 },
    "expression": "happy",
    "expressionWeights": { "happy": 0.7 },
    "gestureClip": "wave",
    "gazeTarget": "towards_user",
    "intensity": 0.7,
    "fadeMs": 220
  }
  ```
- Clip-fallback chain: `<emotion>_<state>_speaking → <state>_speaking
  → <emotion>_<state> → <state> → idle`. De-duped, idle always
  terminal.
- `expression_weights(emotion, intensity)` mirrors the frontend's
  `expressions.ts` and scales by clamped intensity.
- `resolve_asset` resolution order: `runtime_cfg.asset` →
  `pack.metadata.asset` → convention
  `/static/characters/{pack.id}/character.{vrm|gltf}`.
- Gestures: well-known set (`wave`, `nod`, `shake`, `shrug`, `point`,
  `thumbs_up`, `thumbs_down`); unknown gestures are dropped silently.
  Packs override via `runtime_cfg.gestures[<gesture>]`.

`ThreeJSAvatarAdapter` mirrors `Sprite2DAvatarAdapter`'s shape.
Capabilities are `{"3d", "gestures", "gaze", "expressions"}`.
`load_character` accepts (and logs once) packs whose `kind` isn't
VRM/glTF, then still loads — same "never raise" rule as Sprite2D.
`apply_directive` swallows projector + bridge errors.

Registered via the `openmimicry.contracts.avatar_runtime` entry point
as `threejs`.

### Backend wiring

`apps/backend/.../wiring.py` selects the adapter when
`avatar.runtime == "threejs"` and forwards
`config.avatar.runtimes.threejs` as the runtime config. No other
backend file changed.

### Contract test

`tests/contract/test_avatar_runtime.py` widens the hermetic guard
from `{"mock", "sprite2d"}` to `{"mock", "sprite2d", "threejs"}`.
`load_character` now uses `tests/fixtures/packs/good_pack` for the
two file-backed adapters so the round-trip body actually exercises
the full path on every modality.

### Frontend — Three.js runtime

```
apps/desktop/frontend/src/runtimes/threejs/
  ThreeJSRuntime.tsx
  scene.ts          // createScene / configureCamera / attachLighting
  vrm.ts            // VRM loader via @pixiv/three-vrm (dynamic import)
  gltf.ts           // generic glTF loader (dynamic import)
  expressions.ts    // resolveExpression / mergeWeights
  clips.ts          // pickClip / pickGestureClip / clipFallbackChain
  types.ts          // CharacterController (duck-typed)
  index.ts
  __tests__/
    expressions.test.ts
    clips.test.ts
    scene.test.ts
    ThreeJSRuntime.test.tsx
```

- `CharacterController` is the duck-typed interface that VRM and
  glTF loaders both implement; the rest of the runtime never
  branches on `kind`.
- `ThreeJSRuntime.tsx` mounts under `<AvatarHost />`, async-loads
  the asset (cancel-on-unmount), and dispatches `playClip` +
  `setExpression` + `setGazeTarget` on every directive. A gesture
  clip is layered on top when one is named and the manifest knows
  it.
- Renders a `Loading…` label while the asset is in flight and a
  `role="alert"` error label on load failure.
- Both loaders use **dynamic** imports so `three` and `three-vrm`
  end up in their own bundle chunks — only paid for when the
  user actually switches to the Three.js runtime.

`runtimes/registry.ts` adds `"threejs": ThreeJSRuntime`.

`package.json` deltas:
- `three` ^0.169.0
- `@types/three` ^0.169.0
- `@pixiv/three-vrm` ^3.4.0

### Demo pack

`characters/octomimic_vrm/`:
- `pack.yaml` (kind: `vrm`, metadata pointing at `octomimic.vrm`).
- `preview.png` (copied from the M3 sprite2d octomimic so the panel
  has something to show).
- `README.md` explains how to drop in a real VRM. The binary is
  intentionally not committed.

### Tests

Python (un-skipped contract + unit suite):
- `tests/contract/test_avatar_runtime.py` — round-trip now covers
  mock + sprite2d + threejs.
- `tests/unit/avatar/runtimes/test_threejs_projection.py` — every
  projector helper (clip fallback chain, pick_clip with missing
  manifest, expression scaling, intensity clamping, asset resolution
  order, known-gesture allowlist, per-pack gesture remap, gaze
  override).
- `tests/unit/avatar/runtimes/test_threejs_adapter.py` — adapter
  end-to-end against a `FakeBridge`: apply_directive, start/stop
  speaking, set_text, set_visibility, bridge errors swallowed,
  no-pack drops quietly, healthcheck idempotency, factory shape,
  WSBridge Protocol satisfaction, non-Three-friendly pack still
  loads.

Frontend (Vitest with `jsdom`):
- `expressions.test.ts` — scaling, clamping, fresh-object,
  unknown-emotion graceful fallback.
- `clips.test.ts` — fallback chain, pick_clip miss-on-manifest,
  gesture_ prefix, null/empty gesture.
- `scene.test.ts` — `vi.mock("three", ...)` stubs every constructor;
  asserts `setSize`/`setPixelRatio`/`dispose` get called, custom
  camera config is applied, every lighting preset adds the expected
  light count.
- `ThreeJSRuntime.test.tsx` — injected loader, initial directive
  triggers `playClip`/`setExpression`/`setGazeTarget`, rerender
  swaps clips, gesture clip layered, loader rejection renders an
  `role="alert"`, dispose on unmount.

### Bundle size note

Three.js + three-vrm are imported **dynamically** (inside
`defaultLoad()` of `ThreeJSRuntime.tsx`), so the default `/panel`
bundle is unaffected. The Three.js chunk lands lazily the first
time `avatar.runtime: threejs` is in play. Indicative sizes from
upstream releases:

| Package           | Min+gzip | Min   |
|-------------------|----------|-------|
| `three` 0.169     | ~150 kB  | ~600 kB |
| `@pixiv/three-vrm`| ~40 kB   | ~140 kB |
| `three-stdlib`    | (not pulled — examples/jsm only) | — |

(Numbers come from the published bundles; re-confirm with
`pnpm --filter @openmimicry/desktop-frontend build --report` once
the lockfile has been regenerated.)

### Out of scope

- Hand-tracking / mouth-shape / live audio-driven animation (M10).
- Unity bridge (M11), external renderers (M12).
- Bundling a binary VRM. The demo pack ships with instructions; CI
  doesn't fetch the binary either.

Closes the M9 task.
