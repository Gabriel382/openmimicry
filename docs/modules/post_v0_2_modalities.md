# Post-v0.2.0 modality briefs: M10, M11, M12

This file holds three concise module briefs for modalities that ship after v0.2.0. Each can be picked up in parallel once M9 (Three.js) is stable, because every modality talks the same `AvatarRuntimeAdapter` Protocol and consumes the same `AvatarDirective` schema.

Each section follows the standard brief template, abbreviated where the pattern repeats. Anything not stated explicitly inherits the conventions of `M4_avatar_sprite2d.md` and `M9_avatar_threejs.md`.

---

## Module M10: `Live3DAvatarAdapter`

### Goal (1 line)

Add the Live 3D modality: audio-driven mouth, procedural idle motion, gaze-target tracking, and intensity-driven blend weights — all on top of M9's Three.js scene.

### Scope and non-scope

**In scope.**

- Frontend module `apps/desktop/frontend/src/runtimes/live3d/` extending the M9 scene with:
  - Mouth driver: amplitude-based (from the TTS audio playing in the overlay) or viseme-based (from textual hints).
  - Procedural idle: tiny breathing, micro-saccades.
  - Gaze: `gaze: "towards_user" | "away" | "down"` resolved to a head/eye target.
  - Intensity-driven blend weights (a "subtle smile" vs a "broad smile").
- Python `Live3DAvatarAdapter` that publishes a richer projection (or the same projection with `runtime: "live3d"` and additional `live` keys).
- Configuration block `avatar.runtimes.live3d.{mouth_driver, gaze_driver, procedural_idle, blend_window_ms}` already in [`../configuration.md`](../configuration.md).

**Non-scope.**

- Webcam-based user-awareness (deferred; needs its own brief).
- Hand tracking, body pose.

### Inputs

- `AvatarRuntimeAdapter` Protocol (`contracts.md` §5).
- `AvatarDirective` (`contracts.md` §2.3) including `intensity`, `gaze`, `duration_ms`.
- The Three.js scene from M9.
- TTS audio stream available in the overlay window (via `<audio>` element or Web Audio API).

### Outputs

```text
packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/live3d/
  adapter.py
  projection.py

apps/desktop/frontend/src/runtimes/live3d/
  Live3DRuntime.tsx          # extends ThreeJSRuntime
  mouth/
    amplitude.ts             # Web Audio analyser -> jaw weight
    viseme.ts                # text/phoneme -> viseme weights (optional)
  idle.ts                    # procedural idle
  gaze.ts                    # gaze target solver
  expressions.ts             # blends with intensity
  __tests__/
```

### Mocks

Reuses M3's `MockAvatarRuntimeAdapter`. Frontend tests mock the Web Audio API.

### Test surface

- Mouth driver opens/closes proportional to RMS amplitude with a low-pass filter.
- Procedural idle does not run while a `gesture` clip is playing (avoid double motion).
- Gaze interpolates over `blend_window_ms` (no snapping).

### Step-by-step plan

1. Extend M9's `ThreeJSRuntime.tsx` via composition (do not modify it). `Live3DRuntime` mounts the same scene and adds drivers.
2. Implement `mouth/amplitude.ts`: an `AnalyserNode` on the WebAudio output node; smoothed RMS → `mouthOpen` weight in [0, 1].
3. Optional `mouth/viseme.ts`: receive viseme hints over WS (additive wire message `tts.viseme`, ship as a Stable contracts amendment) and map to VRM viseme weights.
4. Implement `idle.ts`: gentle sine waves on neck/shoulder bones, micro-saccade timers on the eye target.
5. Implement `gaze.ts`: target position interpolation; cancel on new `gaze`.
6. Implement `expressions.ts` extension: respect `intensity` as a scalar multiplier.
7. Python `Live3DAvatarAdapter`: same as `ThreeJSAvatarAdapter` with `runtime: "live3d"` and the additional config block in the projection.
8. Vitest tests with mocked AudioContext.
9. Register entry point.
10. Update `docs/avatar_modalities.md` §1.4 with M10 status.

### Definition of done

- [ ] `avatar.runtime: live3d` config produces a visibly more alive character (mouth moves with TTS, breathing visible at idle).
- [ ] No regressions in Three.js-only mode.
- [ ] Contract test passes.
- [ ] Bundle size impact documented.

### Recommended LLM brief

> Implement Module M10 (Live3D) of OpenMimicry. Read `docs/modules/post_v0_2_modalities.md` (the M10 section), `docs/modules/M9_avatar_threejs.md`, and `docs/avatar_modalities.md` §1.4. Build on M9 by composition — do not modify the Three.js runtime. The mouth driver is amplitude-based by default. Open the PR `feat(avatar): M10 — Live3DAvatarAdapter`. Skip-conditions: do not introduce ML models; do not touch sibling Python packages other than `openmimicry-core`.

---

## Module M11: `UnityAvatarAdapter` (bridge)

### Goal (1 line)

Run a separate Unity application as the renderer; the OpenMimicry backend pushes `AvatarDirective`s to Unity over WebSocket (or HTTP / local TCP / named pipes) and Unity drives an Animator + blend trees + facial expressions on its side.

### Scope and non-scope

**In scope.**

- Python `UnityAvatarAdapter` that opens a connection to the configured Unity endpoint and forwards `apply_directive(d)` as a JSON frame.
- A sample Unity project under `apps/unity-bridge/` with:
  - A WebSocket client that consumes the directive JSON.
  - A controller MonoBehaviour mapping `directive.state + directive.emotion + directive.gesture` to Animator parameters and triggers.
  - A small example scene with a placeholder character.
- A reverse channel: Unity acks each directive (`{"type":"ack","handle":"..."}`) for backpressure.

**Non-scope.**

- Bundling Unity binaries with the Python install. Unity must be installed by the user.
- Cross-platform Unity packaging (initially Windows + macOS; Linux later).

### Inputs

- `AvatarRuntimeAdapter` Protocol (`contracts.md` §5).
- `AvatarDirective` (`contracts.md` §2.3).
- The Unity bridge wire-protocol (additive Stable amendment to `contracts.md`):

```json
// backend -> unity
{ "type": "avatar.directive", "runtime": "unity", "directive": { ... } }
{ "type": "load.character", "id": "knight", "asset_url": "..." }
{ "type": "set.visibility", "visible": true }
// unity -> backend
{ "type": "ack", "for": "avatar.directive" }
{ "type": "telemetry", "fps": 60.2, "anim_state": "Speaking" }
```

### Outputs

```text
packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/unity/
  adapter.py
  transports.py            # ws | http | tcp | pipe transports

apps/unity-bridge/
  Assets/OpenMimicry/
    Scripts/
      WSClient.cs
      Directive.cs
      AvatarController.cs
    Scenes/
      Sample.unity
    Prefabs/
      PlaceholderCharacter.prefab
  ProjectSettings/
  README.md
```

### Mocks

Reuses M3's `MockAvatarRuntimeAdapter`. The Unity adapter ships with a `MockUnityTransport` for unit tests (no Unity process needed in CI).

### Test surface

- Adapter sends a well-formed directive frame over `MockUnityTransport`.
- Reconnection logic: drop the transport, the adapter retries with exponential backoff, and queues directives in the meantime (bounded queue, drop-with-warning).
- `swap_runtime` from Three.js → Unity sends `set.visibility=false` to Three.js, opens Unity, and replays the current directive.

### Step-by-step plan

1. Add the Unity wire-protocol amendment to `contracts.md` §9.
2. Implement `transports.py` with abstract `UnityTransport` and concrete `WSUnityTransport`, plus a `MockUnityTransport`.
3. Implement `adapter.py::UnityAvatarAdapter`. Constructor receives a transport. `apply_directive`, `load_character`, `set_visibility`, `shutdown` — each sends a JSON frame.
4. Implement reconnection + bounded queue in the adapter.
5. Implement the Unity-side `WSClient.cs` + `AvatarController.cs` mapping JSON directives to Animator parameters. Ship a `Sample.unity` scene.
6. Document the Unity setup in `apps/unity-bridge/README.md` with screenshots.
7. Register entry point for `openmimicry.contracts.avatar_runtime`.
8. Add unit tests with `MockUnityTransport`. Manual smoke test: run Unity, run the backend, see the placeholder character animate.
9. Update `docs/avatar_modalities.md` §1.5 with M11 status.

### Definition of done

- [ ] Unity sample scene reacts to `avatar.directive` JSON in real time.
- [ ] Adapter passes the contract test against `MockUnityTransport`.
- [ ] Reconnect after a Unity restart within 3s.
- [ ] No required Unity install for Python users who don't choose this modality (lazy transport import).
- [ ] `docs/avatar_modalities.md` §1.5 updated.

### Recommended LLM brief

> Implement Module M11 (Unity bridge) of OpenMimicry. Read `docs/modules/post_v0_2_modalities.md` (M11 section), `docs/avatar_modalities.md` §1.5, and the Unity Animator and WebSocket docs. Ship Python adapter + sample Unity project. Do not bundle Unity binaries. Do not modify other modules. Open the PR `feat(avatar): M11 — UnityAvatarAdapter + sample bridge`. The Unity project lives outside the Python packages; CI does not build it (Unity Cloud Build can be added later).

---

## Module M12: `ExternalAvatarAdapter`

### Goal (1 line)

Generic protocol-based bridge to third-party renderers (VTube Studio-like, Blender, Unreal, browser-based pets) without baking any of them into OpenMimicry — just a documented WebSocket protocol and an adapter that speaks it.

### Scope and non-scope

**In scope.**

- Python `ExternalAvatarAdapter`: opens the configured endpoint, speaks the wire protocol, surfaces health/reconnection.
- The wire protocol spec documented as a frozen surface in `contracts.md` §9 (additive amendment, Stable).
- A small reference "external echo server" in `apps/external-echo/` that logs every directive — useful for third-party developers to test their integration against.
- Documentation page `docs/external_runtimes.md` describing how to write a compliant renderer (Unity-flavour and browser-flavour worked examples).

**Non-scope.**

- Any specific third-party renderer implementation. M12 is the protocol + bridge; users plug in whatever renderer they like.

### Inputs

- `AvatarRuntimeAdapter` Protocol (`contracts.md` §5).
- `AvatarDirective` (`contracts.md` §2.3).
- External wire-protocol amendment (this PR adds it):

```json
// backend -> external
{ "type": "avatar.directive", "runtime": "external", "directive": {...} }
{ "type": "load.character",   "id": "...", "asset_url": "..." }
{ "type": "set.visibility",   "visible": true }
{ "type": "set.text",         "text": "..." }
{ "type": "shutdown" }
// external -> backend
{ "type": "ack",       "for": "..." }
{ "type": "ready" }
{ "type": "error",     "message": "..." }
```

### Outputs

```text
packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/external/
  adapter.py
  client.py            # generic WS client with reconnect

apps/external-echo/
  package.json
  src/server.ts        # Node WS echo server; logs every directive
  README.md

docs/external_runtimes.md
```

### Mocks

`MockExternalServer` (Python) that runs an in-process WS server for tests.

### Test surface

- Round-trip: adapter sends a directive, mock server receives, sends `ack`, adapter records latency.
- Reconnect after server restart.
- Backpressure: server holds acks; adapter's bounded queue grows but doesn't crash; the oldest directive is dropped with a warning after `cfg.max_queue`.

### Step-by-step plan

1. Amend `contracts.md` §9 with the External protocol (additive Stable).
2. Implement `external/client.py` (reconnecting WS client) and `adapter.py`.
3. Implement `apps/external-echo/` as a tiny Node WS server: 50 lines. Used by manual smoke tests and as a developer aid.
4. Write `docs/external_runtimes.md` with a Unity worked example pointer (M11) and a browser worked example (`<iframe>` that listens to the WS and renders a CSS sprite).
5. Register entry point.
6. Unit tests using `websockets.serve` for `MockExternalServer`.
7. Update `docs/avatar_modalities.md` §1.6 with M12 status.

### Definition of done

- [ ] The reference echo server logs received directives.
- [ ] Adapter reconnects within 3s.
- [ ] `docs/external_runtimes.md` published with two worked examples.
- [ ] Contract test passes against `MockExternalServer`.

### Recommended LLM brief

> Implement Module M12 (External avatar adapter) of OpenMimicry. Read `docs/modules/post_v0_2_modalities.md` (M12 section) and `docs/avatar_modalities.md` §1.6. Add the external wire-protocol amendment to `contracts.md` §9. Build the Python adapter, the Node echo server reference implementation, and the `docs/external_runtimes.md` page. The protocol additions must be Stable (not Frozen) for one minor version while we collect feedback. Open the PR `feat(avatar): M12 — ExternalAvatarAdapter + protocol spec + echo server`.

---

## Coordinating M10 / M11 / M12

The three modules are parallel and independent. Each one's only contact with the others is:

- They all read the **same** `AvatarDirective` schema.
- They all subclass / compose the **same** `AvatarRuntimeAdapter` Protocol.
- They each **amend** `contracts.md` §9 additively for their runtime-specific wire fields. Amendments are Stable; renaming an existing field is Frozen and requires `schema_version` bump.

Anyone picking up any of the three should treat `docs/contracts.md` as read-only except for an additive amendment specific to their runtime, and should never modify the other two modules' folders.
