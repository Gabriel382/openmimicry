# feat(avatar): M10 — Live3DAvatarAdapter

Implements `docs/modules/post_v0_2_modalities.md` (M10 section). Third
concrete `AvatarRuntimeAdapter` — same Three.js scene as M9 plus
client-side drivers for audio-driven mouth, procedural idle, and
gaze-target tracking.

## What lands

### Python — `Live3DAvatarAdapter`

```
packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/live3d/
  __init__.py
  adapter.py
  projection.py
```

`build_live3d_projection` reuses `build_threejs_projection` and
appends a `live` block:

```json
{
  "runtime": "live3d",
  "asset": { /* same as M9 */ },
  "clip": "happy_speaking",
  "expressionWeights": { "happy": 0.7 },
  "live": {
    "mouth_driver": "amplitude" | "viseme" | "off",
    "gaze_driver":  "smooth" | "snap" | "off",
    "procedural_idle": true,
    "blend_window_ms": 200,
    "intensity": 0.7,
    "amplitude": { "smoothing_ms": 80, "gain": 1.0, "open_curve": 1.0 },
    "viseme":    { "smoothing_ms": 60, "default": "neutral" },
    "idle":      { "breathing_amplitude": 0.02, "breathing_period_ms": 4200,
                   "saccade_min_ms": 900, "saccade_max_ms": 2200 },
    "gaze_target": "towards_user"
  }
}
```

- Unknown driver names fall back to safe defaults (`"telepathy"` → `"amplitude"`).
- Every numeric is bounded (`blend_window_ms ∈ [0, 10_000]`, `gain ∈ [0, 10]`,
  …) — the projector accepts garbage configs and never raises.
- `directive.intensity` is clamped into `[0, 1]` and propagates as
  `live.intensity`.

`Live3DAvatarAdapter` composes the M9 pack-load + bridge pipeline. Same
"never raise" rule for unknown gestures, non-3D-friendly pack kinds,
and bridge errors. Capabilities are `{"3d", "gestures", "gaze",
"expressions", "mouth", "procedural_idle"}`.

Registered via `openmimicry.contracts.avatar_runtime` as `live3d`.

### Backend wiring

`apps/backend/.../wiring.py` selects `Live3DAvatarAdapter` when
`avatar.runtime == "live3d"` and forwards `config.avatar.runtimes.live3d`
as `runtime_cfg`. No other backend file changed.

### Contract test

`tests/contract/test_avatar_runtime.py` widens the hermetic guard to
`{"mock", "sprite2d", "threejs", "live3d"}`. The round-trip body
already runs against `tests/fixtures/packs/good_pack` so every modality
exercises `load_character → apply_directive(s) → shutdown`.

### Frontend — Live3D runtime

```
apps/desktop/frontend/src/runtimes/live3d/
  Live3DRuntime.tsx          # composition over <ThreeJSRuntime />
  mouth/amplitude.ts         # createAmplitudeDriver
  mouth/viseme.ts            # createVisemeDriver
  idle.ts                    # createIdleDriver (breathing + saccades)
  gaze.ts                    # createGazeDriver (interpolation + snap)
  expressions.ts             # blendExpression(base + server + mouth + viseme)
  index.ts
  __tests__/
    amplitude.test.ts
    idle.test.ts
    gaze.test.ts
    expressions.test.ts
```

- `Live3DRuntime` renders M9's `<ThreeJSRuntime />` verbatim and adds
  driver lifecycles + a per-frame tick loop. The brief is explicit:
  build on M9 by **composition**, do not modify the Three.js runtime.
- Drivers tick on `requestAnimationFrame` (pluggable for tests).
- The composed projection is forwarded to `<ThreeJSRuntime />` with
  `runtime: "threejs"` and merged `expressionWeights` so the
  `CharacterController` sees one final weight map.
- `data-*` attributes on the wrapping `<div>` expose driver outputs
  (`data-mouth`, `data-breathing`, `data-gaze-{x,y,z}`, `data-gesture`)
  so tests + dev tooling can observe state without peeking at the
  Three.js scene.

Driver details:

- **Amplitude** (`mouth/amplitude.ts`) — `AnalyserNode` time-domain
  RMS, gain + power curve + clamp, one-pole low-pass with time
  constant = `smoothing_ms`. Wall-clock dt comes from a pluggable
  `now()` so tests step deterministically.
- **Viseme** (`mouth/viseme.ts`) — receives `{viseme, weight}` frames
  (additive contracts amendment landing in a follow-up PR), smooths
  the multi-key weight table over `smoothing_ms`. Pack overrides via
  `runtime_cfg.viseme.map`.
- **Idle** (`idle.ts`) — sine-wave breathing (`breathing_amplitude`
  bounded; period in ms), scheduled micro-saccades drawn from
  `[saccade_min_ms, saccade_max_ms]`. `pauseWhileGesture(true)` pins
  the last sample, satisfying "Procedural idle does not run while a
  `gesture` clip is playing".
- **Gaze** (`gaze.ts`) — `setTarget(name)` interpolates from current
  to target over `blendWindowMs`; `snap(name)` skips the blend; pack
  overrides via `runtime_cfg.map`.
- **Blend** (`expressions.ts`) — layers base emotion (M9
  `resolveExpression` × `intensity`) + server weights + amplitude
  mouth + viseme weights. Later inputs override earlier ones for the
  same key (no additive blending past 1).

### Registry

`apps/desktop/frontend/src/runtimes/registry.ts` adds
`"live3d": Live3DRuntime`. `setRuntime`/`getRuntime` cover all three
modalities.

### Tests

Python:
- `tests/unit/avatar/runtimes/test_live3d_projection.py` — every
  driver block, unknown driver fallback, int/bool/float coercion +
  clamping, directive gaze + intensity propagation, default vs.
  overridden gaze, runtime_cfg=None safety.
- `tests/unit/avatar/runtimes/test_live3d_adapter.py` — Protocol
  satisfaction, runtime+capabilities, apply_directive end-to-end
  against a `FakeBridge`, runtime_cfg disables drivers, no-pack
  drop, bridge errors swallowed, start/stop speaking, set_text +
  visibility, healthcheck/shutdown idempotency, pack-load with a
  non-3D-friendly fixture, factory shape, `WSBridge` Protocol
  satisfaction.
- `tests/contract/test_avatar_runtime.py` — guard widened to
  include `"live3d"`.

Vitest:
- `amplitude.test.ts` — silent input → 0, smoothed ramp under
  sustained amplitude, clamp at high gain, decay back to zero,
  dispose() freezes the sample.
- `idle.test.ts` — breathing wave is bounded, no saccade while
  paused, saccade fires after the configured interval and stays in
  `[-1, 1]`, reset() clears state.
- `gaze.test.ts` — blend interpolates without snapping, converges
  after `blendWindowMs`, `snap()` jumps, pack-override targets,
  unknown name leaves state in place, mid-blend target swap works.
- `expressions.test.ts` — amplitude curve, base + server + mouth +
  viseme layering precedence, clamp to `[0, 1]`.

### Bundle size

No new runtime dependencies (the drivers are pure TypeScript +
Web Audio). The Live3D bundle inherits Three.js + three-vrm's lazy
chunk from M9; M10 adds ~10 kB of driver code (gzipped). Re-confirm
with `pnpm --filter @openmimicry/desktop-frontend build --report`
once the lockfile is regenerated.

### Out of scope

- Webcam-based user-awareness (deferred; needs its own brief).
- Hand tracking / body pose.
- `tts.viseme` WS amendment + backend producer (a follow-up PR
  lands the additive wire-protocol entry once the M2 voice stack
  has a viseme source; the driver is ready to consume it).

Closes the M10 task.
