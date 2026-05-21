# Writing a compliant External avatar renderer (M12)

The `ExternalAvatarAdapter` is a thin generic bridge: OpenMimicry's
backend connects to your renderer over WebSocket, forwards directives,
and consumes reverse-channel acks. The protocol is small enough to
implement in any language with a WS library — Unity (C#), Blender
(Python in-process), Unreal (C++ / Blueprints), a browser pet (JS),
anything that can open a socket.

This page is the canonical "how do I make X talk to OpenMimicry"
reference. The wire shape itself is also documented as the additive
amendment to `docs/contracts.md` §9.

## Status

**Stable.** Additive changes only without a `schema_version` bump.
Renaming an existing field is **Frozen** and requires the contracts-
change procedure (see `docs/contracts.md` §11). The fields described
below will not change names within a minor version.

## Setup on the OpenMimicry side

```yaml
# app.yaml
avatar:
  runtime: external
  runtimes:
    external:
      url: ws://127.0.0.1:8765
      # optional, forwarded verbatim on `load.character` frames:
      asset_url: https://example.test/octomimic.glb
```

The OpenMimicry backend (M6) plus the `ExternalAvatarAdapter` are
enough. The optional install:

```bash
pip install "openmimicry-avatar[external]"
```

pulls in `websockets`. Without it the adapter logs a `ExternalUnavailable`
warning and stops the sender loop; the rest of the system keeps running.

## The protocol

### Backend → renderer (sent by the adapter)

| `type`              | Fields                                                             | When                                            |
|---------------------|--------------------------------------------------------------------|-------------------------------------------------|
| `avatar.directive`  | `runtime: "external"`, `directive: { state, emotion, speaking, ... }` | Every time the director emits a new directive. |
| `load.character`    | `id: string`, `asset_url: string \| null`                          | On `avatar.load_character()`.                   |
| `set.visibility`    | `visible: bool`                                                    | On `AvatarRuntime.set_visibility(...)`.         |
| `set.text`          | `text: string`                                                     | On `set_text(...)`. Used for speech-bubble mirroring. |
| `shutdown`          | —                                                                  | Sent best-effort on adapter shutdown.           |

The `avatar.directive` `directive` payload mirrors
`docs/contracts.md` §2.3 exactly. Unknown fields are passed through
verbatim — renderers must ignore (not error on) anything they don't
support.

### Renderer → backend (the reverse channel)

| `type`        | Fields                            | What it does                                                   |
|---------------|-----------------------------------|----------------------------------------------------------------|
| `ready`       | —                                 | Tell the adapter the renderer is ready to receive directives.  |
| `ack`         | `for: string`                     | Per-frame backpressure ack. Increments `acks_received`.        |
| `error`       | `message: string`                 | Surface a non-fatal error. Captured in `errors_received`.      |

`telemetry` from M11 is also accepted (`fps` / `anim_state`) but is
out of scope for M12 — the External adapter ignores it.

### Reconnect behaviour

- The adapter opens the WS on first `apply_directive` / `load_character`.
- On send or read failure the adapter closes the client and retries
  with exponential backoff (250 ms → 5 s).
- The outbound queue is bounded (`max_queue=64`). When the renderer
  is unreachable the **oldest** frame is dropped with a one-shot
  warning so the backend doesn't grow unbounded.
- On a successful reconnect, the adapter resumes from the in-flight
  frame (the one that failed is re-queued at the front).

## Worked example 1 — browser pet

```html
<!doctype html>
<meta charset="utf-8" />
<title>Browser pet</title>
<style>
  .pet { width: 256px; height: 256px; }
  .pet[data-state="speaking"] { filter: drop-shadow(0 0 8px #4caf50); }
  .pet[data-state="thinking"] { filter: drop-shadow(0 0 8px #ffb300); }
</style>

<img class="pet" id="pet" src="/octomimic/idle.png" />

<script type="module">
const PET = document.getElementById("pet");
const URL = "ws://127.0.0.1:8765";

function connect() {
  const ws = new WebSocket(URL);
  ws.addEventListener("open", () => ws.send(JSON.stringify({ type: "ready" })));
  ws.addEventListener("message", (e) => {
    const frame = JSON.parse(e.data);
    if (frame.type === "avatar.directive") {
      const d = frame.directive ?? {};
      PET.dataset.state = d.state ?? "idle";
      ws.send(JSON.stringify({ type: "ack", for: "avatar.directive" }));
    } else if (frame.type === "set.visibility") {
      PET.style.opacity = frame.visible ? "1" : "0";
    } else if (frame.type === "set.text") {
      // Render the bubble in your own UI.
    } else if (frame.type === "shutdown") {
      ws.close();
    }
  });
  ws.addEventListener("close", () => setTimeout(connect, 1000));
}
connect();
</script>
```

That's the whole renderer. Three CSS rules + a 30-line script.

## Worked example 2 — Unity-flavour

See `apps/unity-bridge/Assets/OpenMimicry/Scripts/` for the canonical
implementation. The M11 sample (UnityAvatarAdapter) speaks a
superset of M12's protocol — every M12 frame is a strict subset of
what the Unity-flavour endpoint already understands, with one rename
(`bubble.text` → `set.text`). A renderer can implement either; the
External adapter only sends M12 shapes.

## Worked example 3 — your-favourite-engine

Any engine with WS support can implement the protocol. The Echo
server (`apps/external-echo/`) makes the development loop tight:

```bash
pnpm --filter @openmimicry/external-echo start
# wire your renderer at ws://127.0.0.1:8765 against the same flow
```

Watch the echo server's stdout while you submit chat turns to the
backend, and you have a complete view of what to send and what to
ack.

## Testing your renderer

1. Run the OpenMimicry backend with `avatar.runtime: external` and
   `runtimes.external.url` pointing at your renderer.
2. Submit a chat turn (text input via the panel, or `curl -X POST
   http://localhost:8000/chat -d '{"text":"hi"}'`).
3. Confirm your renderer receives the `avatar.directive` frame and
   sends back an `ack` within a second. Lack of acks doesn't crash
   the backend, but the adapter's outbound queue will eventually
   drop the oldest frame and log a warning.

## What we don't ship in M12

- Authentication. The wire protocol is unauthenticated by design;
  bind to `127.0.0.1` only and trust the local trust boundary. A
  future amendment may add a token preamble.
- Encryption. WS over a localhost socket is enough for the in-process
  trust model. Remote renderers should sit behind a TLS-terminating
  proxy.
- Multi-renderer fan-out. One adapter instance ↔ one renderer. If
  you want N renderers, register N entries under
  `avatar.runtimes.external.*` (post-v0.3 work).
