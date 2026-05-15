# Module M9: `ThreeJSAvatarAdapter` (post-v0.2.0)

## Goal (1 line)

Add a lightweight 3D modality — VRM and glTF/GLB rendered with Three.js inside the same Tauri overlay window — as a second `AvatarRuntimeAdapter`, proving the pluggability story.

## Scope and non-scope

**In scope.**

- Python: `ThreeJSAvatarAdapter` that consumes `AvatarDirective` and publishes a Three.js-flavoured projection over the WebSocket.
- Frontend: `apps/desktop/frontend/src/runtimes/threejs/ThreeJSRuntime.tsx` — a Three.js scene mounted inside the existing overlay window, loading the configured VRM/glTF/GLB asset, running idle/listening/thinking/speaking animation clips, mapping `directive.state + directive.emotion + directive.intensity` to clip selection and blend weights.
- A small VRM expression mapper (uses `three-vrm` if VRM is loaded; falls back to morph targets for plain glTF).
- Camera + lighting presets configurable via `avatar.runtimes.threejs`.
- One bundled glTF demo asset for the README screenshot ("OctomimicVRM").

**Non-scope.**

- Live mouth/audio-driven animation (M10 Live3D owns).
- Hand-tracking / webcam awareness (M10).
- Unity bridge (M11).
- External renderers (M12).

## Inputs (immutable, from contracts.md)

- `AvatarRuntimeAdapter` Protocol (`contracts.md` §5).
- `AvatarDirective` schema including the optional 3D-relevant fields (`gesture`, `gaze`, `intensity`, `duration_ms`) (`contracts.md` §2.3).
- `AvatarConfig.runtimes.threejs` from [`../configuration.md`](../configuration.md).
- The wire protocol message `avatar.directive` with `runtime: "threejs"` (additive extension of `contracts.md` §9; ship as a Stable amendment in this PR).

## Outputs (this module owns)

Python:

```text
packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/threejs/
  __init__.py
  adapter.py              # ThreeJSAvatarAdapter
  projection.py           # build_threejs_projection(directive, runtime_cfg)
tests/unit/avatar/runtimes/
  test_threejs_adapter.py
  test_threejs_projection.py
```

Frontend:

```text
apps/desktop/frontend/src/runtimes/threejs/
  ThreeJSRuntime.tsx
  scene.ts                # scene/camera/lighting setup
  vrm.ts                  # VRM loading via @pixiv/three-vrm
  gltf.ts                 # generic glTF/GLB loading
  expressions.ts          # emotion -> VRM expression weights
  clips.ts                # state -> animation clip selection
  __tests__/
    expressions.test.ts
    clips.test.ts
    scene.test.ts
```

Plus an entry in `apps/desktop/frontend/src/runtimes/registry.ts` mapping `"threejs"` → `ThreeJSRuntime`.

A small example asset:

```text
characters/octomimic_vrm/
  pack.yaml               # kind: vrm
  octomimic.vrm
  preview.png
```

## Mock implementations this module provides

None new; reuses `MockAvatarRuntimeAdapter` from M3 for backend tests. Frontend tests use a `vi.mock("three")` setup so the actual GL pipeline isn't required in CI.

## Test surface

- **Contract (Python).** `ThreeJSAvatarAdapter` passes `tests/contract/test_avatar_runtime.py` with all fields populated (`gesture`, `gaze`, `intensity`).
- **Unit (Python).** `build_threejs_projection` translates `directive.state == "speaking" && directive.emotion == "happy" && intensity == 0.7` into the expected `{ clips: [...], blendWeights: {...}, expression: "happy" }` shape.
- **Unit (Frontend).** `expressions.ts::resolveExpression(directive)` returns the right VRM expression weights table.
- **Unit (Frontend).** `clips.ts::pickClip(state, gesture)` picks the right glTF animation clip name with documented fallback when the clip is missing.
- **Unit (Frontend).** `ThreeJSRuntime` mounts a renderer (mocked), receives a directive, calls into the clip player. No real GL in CI.

## Step-by-step plan (atomic, numbered)

1. Add an additive entry to `docs/contracts.md` §9 for the Three.js projection. Land as a `contracts: amendment` PR before starting this one if needed.
2. Implement `projection.py::build_threejs_projection(directive, runtime_cfg)`:
   ```json
   {
     "type": "avatar.directive",
     "runtime": "threejs",
     "directive": { /* AvatarDirective */ },
     "clip": "happy_speaking",
     "blendWeights": { "talk": 0.8, "happy": 0.6 },
     "expression": "happy",
     "gestureClip": "wave",
     "gazeTarget": "towards_user"
   }
   ```
3. Implement `adapter.py::ThreeJSAvatarAdapter`. Same shape as `Sprite2DAvatarAdapter` but emitting the Three.js projection. `load_character(id, cfg)` validates the pack's `kind == "vrm" | "gltf"` and includes the asset URL in the projection so the frontend knows what to load.
4. Register via entry point `openmimicry.contracts.avatar_runtime`.
5. Add npm deps to `apps/desktop/frontend/package.json`: `three`, `@pixiv/three-vrm`, `three-stdlib`.
6. Implement frontend `scene.ts`: create renderer with `alpha: true` for transparent background, configure camera from `runtime_cfg.camera`, add lights per `runtime_cfg.lighting` preset (`studio`, `outdoor`, `flat`).
7. Implement `vrm.ts` to load `.vrm` assets via `@pixiv/three-vrm`. Expose `setExpression(weights)` and `playClip(name, fade)`.
8. Implement `gltf.ts` for plain glTF/GLB. Expose the same interface as `vrm.ts` (duck-typing) so the rest of the code doesn't branch.
9. Implement `expressions.ts`: dictionary `emotion -> Partial<VRMExpressionWeights>`. `intensity` scales the weights. Default neutral when unset.
10. Implement `clips.ts`: dictionary `(state, gesture | null) -> clipName` with documented fallback (`<state>_speaking` → `<state>` → `idle`).
11. Implement `ThreeJSRuntime.tsx`: mounts the renderer in the `<div>` provided by `<AvatarHost>`. RAF loop pausing on `tauri.event.listen("window-hidden")`. Subscribes to `avatar.directive` via `useAvatarDirective`. On change: fade to the new clip, apply expression, set gaze.
12. Add `apps/desktop/frontend/src/runtimes/registry.ts` entry for `"threejs"`.
13. Vitest tests with `vi.mock("three", ...)` for the unit tests; full GL is not exercised in CI.
14. Build the bundled demo asset `characters/octomimic_vrm/`. Document its license in `pack.yaml`.
15. Update `docs/avatar_modalities.md` §1.3 with a footnote that M9 is done.
16. Update `CHANGELOG.md` under v0.3.0 (or whichever post-v0.2 minor we tag).
17. `make ci`. Open PR `feat(avatar): M9 — ThreeJSAvatarAdapter + frontend Three.js runtime`.

## Definition of done (checklist)

- [ ] `avatar.runtime: threejs` in YAML config makes the overlay render a VRM model.
- [ ] Switching pack between `octomimic` (sprite2d) and `octomimic_vrm` (threejs) via `/runtime/swap` works without restart.
- [ ] `ThreeJSAvatarAdapter` passes the contract test.
- [ ] Frontend unit tests pass with mocked Three.js.
- [ ] One README screenshot exists showing the same character in Sprite2D and Three.js side by side.
- [ ] Bundle size delta documented in PR description (Three.js + three-vrm).
- [ ] `CHANGELOG.md` entry under v0.3.0.

## Recommended LLM brief (copy-pasteable prompt)

> You are implementing **Module M9 (`ThreeJSAvatarAdapter`)** of OpenMimicry — the second avatar modality after Sprite2D. M3 (avatar core) and M4 (Sprite2D) have landed; the orchestrator can already swap runtimes.
>
> Read in order:
>
> 1. `docs/contracts.md` §2.3, §5, §9 — `AvatarDirective` with its 3D-relevant fields, the Protocol, the wire protocol.
> 2. `docs/modules/M9_avatar_threejs.md` — this brief.
> 3. `docs/avatar_modalities.md` §1.3, §2 — the modality definition and the adapter contract context.
> 4. `@pixiv/three-vrm` docs: https://github.com/pixiv/three-vrm
>
> Implement the 17-step plan. Critical rules:
>
> - The renderer lives **inside** the existing overlay window mount (`<AvatarHost>`'s mount div). Do not open new windows.
> - Pause the RAF loop when the overlay window is hidden (Tauri emits an event).
> - VRM and glTF/GLB share a duck-typed loader interface so the rest of the code doesn't branch.
> - Ignore fields the adapter doesn't support and never raise. Same rule as Sprite2D: an unknown `gesture` is a no-op, not an error.
>
> Open the PR titled `feat(avatar): M9 — ThreeJSAvatarAdapter + frontend Three.js runtime` with the Definition-of-done checklist ticked. Do not touch `apps/desktop/src-tauri/` — M8's territory. Do not modify Sprite2D — that's done.
