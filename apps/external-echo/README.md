# OpenMimicry External-protocol echo server

A reference WS server for developers building a compliant external
renderer (Unity, Blender, Unreal, browser pet, anything). It speaks
the M12 wire protocol documented in `docs/external_runtimes.md` and
`docs/contracts.md` §9 — point the `ExternalAvatarAdapter` at it and
watch every directive land in your terminal.

## Run it

```bash
# from the repo root
pnpm install --frozen-lockfile
pnpm --filter @openmimicry/external-echo start
# server is now listening on ws://127.0.0.1:8765
```

Then in `app.yaml`:

```yaml
avatar:
  runtime: external
  runtimes:
    external:
      url: ws://127.0.0.1:8765
```

Start the backend (`make backend-m6`), submit a chat turn, and watch
the echo server's stdout log every `avatar.directive` frame.

## What it does

- Emits `{ "type": "ready" }` on every new connection.
- Replies to `avatar.directive` with `{ "type": "ack", "for": "avatar.directive" }`.
- Replies to `shutdown` with an ack, then closes the socket.
- Logs every other frame (`load.character`, `set.text`,
  `set.visibility`) to stdout without modifying state.
- Drops malformed JSON with an `error` reply.

## Environment

- `OM_EXTERNAL_HOST` — listen address (default `127.0.0.1`).
- `OM_EXTERNAL_PORT` — listen port (default `8765`).

## Building your own renderer

Read `docs/external_runtimes.md`. The Unity-flavour worked example is
in `apps/unity-bridge/`; the browser-flavour worked example is
documented inline in the doc.
