# feat(avatar): M12 — ExternalAvatarAdapter + protocol spec + echo server

Implements `docs/modules/post_v0_2_modalities.md` (M12 section).
Fifth concrete `AvatarRuntimeAdapter`: a renderer-agnostic
WebSocket bridge that lets third-party renderers (browser pet,
Blender, Unreal, custom Unity, anything) plug into OpenMimicry
without baking it into the core.

## What lands

### Python — `ExternalAvatarAdapter`

```
packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/external/
  __init__.py
  adapter.py
  client.py
```

#### Wire protocol (additive Stable amendment to §9)

```jsonc
// backend → renderer
{ "type": "avatar.directive", "runtime": "external", "directive": { ... } }
{ "type": "load.character",   "id": "...", "asset_url": "..." }
{ "type": "set.visibility",   "visible": true }
{ "type": "set.text",         "text": "..." }
{ "type": "shutdown" }
// renderer → backend
{ "type": "ready" }
{ "type": "ack",   "for": "avatar.directive" }
{ "type": "error", "message": "..." }
```

#### Client interface

`ExternalClient` is a runtime-checkable Protocol with `connect`,
`send(frame)`, `aclose`, `incoming() -> AsyncIterator[frame]`, and
`is_open`. Two concrete clients ship:

- `WSExternalClient(url)` — opens a real WS. `websockets` is
  **lazy-imported** inside `connect()`. Missing extra raises
  `ExternalUnavailable("pip install openmimicry-avatar[external]")`.
- `MockExternalClient()` — records sent frames; tests push the
  reverse channel via `feed_incoming(frame)`. Also supports
  `fail_until_attempt=N` and `simulate_disconnect()`.

#### Adapter

`ExternalAvatarAdapter` mirrors `UnityAvatarAdapter`'s shape:

- Bounded outbound queue (`maxsize=64` by default). Drop-oldest with
  a one-shot warning when the renderer is unreachable.
- Sender loop with exponential backoff (250 ms → 5 s) that re-queues
  the in-flight frame on send failure.
- Reader loop that counts `ready`, `ack`, and surfaces `error` frames
  on `errors_received` (logged at WARN level too).
- Polite `{"type":"shutdown"}` sent best-effort before close.

Capabilities `{"external", "gestures", "gaze", "expressions"}`.
Registered via `openmimicry.contracts.avatar_runtime` as `external`.
Optional install `pip install "openmimicry-avatar[external]"` pulls
in `websockets`.

### Backend wiring

`apps/backend/.../wiring.py` selects `ExternalAvatarAdapter` when
`avatar.runtime == "external"` and forwards
`config.avatar.runtimes.external` as `runtime_cfg`. No other backend
file changed.

### Contract test

`tests/contract/test_avatar_runtime.py` widens the hermetic guard to
`{"mock", "sprite2d", "threejs", "live3d", "unity", "external"}`.
The External factory uses `MockExternalClient` so the round-trip
body stays offline.

### Python tests

`tests/unit/avatar/runtimes/test_external_client.py`:
- Protocol satisfaction for both clients.
- Send-before-connect raises; close yields the sentinel; iterator
  exits cleanly.
- `fail_until_attempt` retries until the threshold.
- `simulate_disconnect` blocks the next send.
- `feed_incoming` round-trips through `incoming()`.
- `WSExternalClient` raises `ExternalUnavailable` when `websockets`
  is missing (monkey-patched).

`tests/unit/avatar/runtimes/test_external_adapter.py`:
- Protocol satisfaction + capabilities.
- Every frame shape — `load.character`, `avatar.directive`,
  `set.text`, `set.visibility`, start/stop-speaking, `shutdown`.
- `healthcheck()` reflects client state.
- `shutdown()` sends the shutdown frame and is idempotent.
- Reconnect after `simulate_disconnect()`.
- Bounded queue drops oldest with one-shot warning when the
  renderer refuses to connect.
- `ack`/`ready`/`error` counters update on every reverse-channel
  frame.
- Factory shape.

### Reference echo server

```
apps/external-echo/
  package.json              # @openmimicry/external-echo (pnpm workspace)
  tsconfig.json
  src/server.ts             # ~50 line WS server using `ws`
  README.md
```

- Emits `{"type":"ready"}` on connect.
- Replies to every `avatar.directive` with
  `{"type":"ack","for":"avatar.directive"}`.
- Replies to `shutdown` with an ack, then closes.
- Logs every other frame to stdout with a short preview.
- `OM_EXTERNAL_HOST` / `OM_EXTERNAL_PORT` env overrides.

`pnpm-workspace.yaml` lists `apps/external-echo` so it ships under
the same security posture (`minimum-release-age=14`,
`block-exotic-subdeps`, `ignore-scripts`). CI does not run the
server; it's a development aid.

### Docs

`docs/external_runtimes.md` is the canonical "how to write a
compliant external renderer" reference:

- Status: Stable, additive-only for one minor version.
- Wire-protocol table (backend → renderer + renderer → backend).
- Reconnect behaviour + bounded-queue contract.
- 30-line browser-pet worked example (HTML + CSS + JS).
- Pointer to the Unity-flavour worked example in `apps/unity-bridge/`
  (M11), with a note that the protocol is a strict subset.
- Testing flow against the echo server.
- Out-of-scope notes (no auth, no encryption, single-renderer).

## Out of scope

- Any specific third-party renderer implementation. M12 is the
  protocol + bridge + echo server.
- Multi-renderer fan-out (one adapter instance ↔ one renderer for
  now).
- Authentication. The wire is unauthenticated by design; bind to
  `127.0.0.1` only and trust the local boundary. A future amendment
  may add a token preamble.

Closes the M12 task.
