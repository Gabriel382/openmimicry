# feat(avatar): M11 — UnityAvatarAdapter + sample bridge

Implements `docs/modules/post_v0_2_modalities.md` (M11 section).
Fourth concrete `AvatarRuntimeAdapter`: a separate Unity process owns
the renderer; the OpenMimicry backend forwards directives over
WebSocket and consumes acks for backpressure.

## What lands

### Python — `UnityAvatarAdapter`

```
packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/unity/
  __init__.py
  adapter.py
  transports.py
```

#### Wire protocol (additive amendment to §9)

```jsonc
// backend → Unity
{ "type": "avatar.directive", "runtime": "unity", "directive": { ... } }
{ "type": "load.character",   "id": "knight", "asset_url": "..." }
{ "type": "set.visibility",   "visible": true }
{ "type": "bubble.text",      "text": "...", "complete": true }
// Unity → backend
{ "type": "ack",       "for": "avatar.directive" }
{ "type": "telemetry", "fps": 60.2, "anim_state": "Speaking" }
```

#### Transport interface

`UnityTransport` is a runtime-checkable Protocol with `connect`,
`send(frame)`, `aclose`, `incoming() -> AsyncIterator[frame]`, and
`is_open`. Two concrete transports ship:

- `WSUnityTransport(url)` — opens a real WebSocket. `websockets`
  is **lazy-imported** inside `connect()` so a pure mocks-only
  install never pulls it in. Missing extra raises
  `UnityTransportUnavailable("pip install openmimicry-avatar[unity]")`.
- `MockUnityTransport()` — records sent frames; tests push the
  reverse channel via `feed_incoming(frame)`. Also supports
  `fail_until_attempt=N` (refuse the first N connects) and
  `simulate_disconnect()` (flip `is_open=False`) so reconnect logic
  is straightforward to exercise.

#### Adapter

`UnityAvatarAdapter` owns:

- A **bounded outbound queue** (`maxsize=64` by default). When the
  queue fills (Unity is unreachable, network paused), the **oldest**
  frame is dropped and a one-shot warning is logged. This mirrors
  the EventBus drop-policy.
- A **sender loop** that reconnects with exponential backoff
  (250 ms → 5 s) and re-queues the in-flight frame on send failure so
  no directive is silently lost across a transient drop.
- A **reader loop** that counts `ack` frames (`acks_received`) and
  captures `telemetry` frames (`telemetry_received`) — surfaces the
  panel UI can subscribe to in a follow-up PR.

Every adapter method (`load_character`, `apply_directive`, `set_text`,
`start_speaking`, `stop_speaking`, `set_visibility`) encodes a JSON
frame matching the amendment above. Unknown directive fields go on
the wire untouched — Unity drops what it doesn't recognise.

Capabilities: `{"3d", "external", "gestures", "gaze", "expressions"}`.
Registered via `openmimicry.contracts.avatar_runtime` as `unity`.

Optional install: `pip install "openmimicry-avatar[unity]"` brings in
`websockets`.

### Backend wiring

`apps/backend/.../wiring.py` selects `UnityAvatarAdapter` when
`avatar.runtime == "unity"` and forwards `config.avatar.runtimes.unity`
as `runtime_cfg`. No other backend file changed.

### Contract test

`tests/contract/test_avatar_runtime.py` widens the hermetic guard to
`{"mock", "sprite2d", "threejs", "live3d", "unity"}`. The Unity
factory uses `MockUnityTransport` so the round-trip body (load →
apply × 2 → shutdown) stays offline.

### Python tests

`tests/unit/avatar/runtimes/test_unity_transports.py`:

- Protocol satisfaction for both transports.
- Send-before-connect raises; close yields the sentinel; iterator
  exits cleanly after close.
- `fail_until_attempt` retries until the threshold.
- `simulate_disconnect()` blocks the next send.
- `feed_incoming(frame)` round-trips through `incoming()`.
- `WSUnityTransport` raises `UnityTransportUnavailable` when the
  optional `websockets` extra is missing (monkey-patched).

`tests/unit/avatar/runtimes/test_unity_adapter.py`:

- Protocol + capabilities.
- Every frame shape — `load.character`, `avatar.directive`,
  `bubble.text`, `set.visibility`, start/stop-speaking toggles.
- `healthcheck()` reflects transport state (closed → False, opened
  → True, after `shutdown()` → False).
- `shutdown()` is idempotent.
- Reconnect after `simulate_disconnect()` — the next directive
  flushes to the freshly-reopened transport.
- Bounded queue drops the oldest frame and emits a one-shot warning
  when Unity refuses to connect.
- `ack` frames increment `acks_received`; telemetry frames land in
  `telemetry_received`.
- Factory returns an adapter with a `MockUnityTransport`.

### Unity sample

```
apps/unity-bridge/
  Assets/OpenMimicry/Scripts/
    WSClient.cs            # System.Net.WebSockets client + ack + telemetry
    Directive.cs           # JsonUtility DTOs for every frame type
    AvatarController.cs    # Animator parameter bridge
  README.md
```

- `WSClient` runs the WS thread on a background `Task` and uses a
  thread-safe queue to marshal inbound frames onto Unity's main
  thread. Reconnects with exponential backoff. Auto-acks
  `avatar.directive` frames; emits `telemetry` every second with
  current FPS + last animation state.
- `AvatarController` translates `directive.state` /
  `directive.emotion` to `Animator` integer parameters, sets the
  `Speaking` bool, fires the `Gesture` trigger, and clamps
  `Intensity` into `[0, 1]`. Optional `Renderer` toggled by
  `set.visibility`; optional UI label mirrors `bubble.text`.
- CI does **not** build the Unity project. The README documents the
  drop-in setup and Unity-version baseline (2022.3 LTS).

## Out of scope

- Bundling Unity binaries with the Python install. Users install
  Unity themselves.
- Cross-platform packaging of the Unity build (out of scope per the
  M11 brief — initial recommendation is Windows + macOS standalone
  players).
- Surfacing `acks_received` / `telemetry_received` over the bus.
  The fields exist now; the bus projector amendment is a one-line
  follow-up.

Closes the M11 task.
