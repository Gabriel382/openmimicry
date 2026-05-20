# feat(desktop-frontend): M7 — overlay/panel routes, WS client, runtime registry

Implements `docs/modules/M7_frontend.md` against the frozen wire protocol
in `docs/contracts.md` §9.

## What lands

### `apps/desktop/frontend/`

```
apps/desktop/frontend/
  package.json              # @openmimicry/desktop-frontend, pnpm 11.x
  tsconfig.json             # strict + noUncheckedIndexedAccess
  vite.config.ts            # proxies /ws, /api, /static -> :8000
  vitest.config.ts          # jsdom + coverage on src/{ws,components,hooks}
  index.html
  README.md
  src/
    main.tsx                # mounts <App /> into #root
    App.tsx                 # HashRouter inside one WSProvider
    ws/
      protocol.ts           # discriminated union mirroring §9 verbatim
      reconnect.ts          # jittered exponential-backoff controller
      WSProvider.tsx        # injectable socket factory + per-type subscribe
      mockSocket.ts         # MockWebSocket + factory for Vitest
    hooks/
      useWS.ts              # context re-export
      useAvatarDirective.ts # latest avatar.directive
      useBubbleText.ts      # partial accumulation; listening clears
      useTaskCards.ts       # Map<id, TaskUpdate> + cancel(id)
      useTauriCommand.ts    # lazy @tauri-apps invoke; no-op in browser
    runtimes/
      registry.ts           # M4 + setRuntime/getRuntime/PlaceholderRuntime
      types.ts              # AvatarRuntimeProps
      sprite2d/              # owned by M4 (unchanged)
    components/
      AvatarHost.tsx
      SpeechBubble.tsx
      TextInput.tsx
      VoiceToggle.tsx
      TaskCard.tsx
      ModeIndicator.tsx
      SettingsPanel.tsx
    routes/
      OverlayRoute.tsx      # /#/overlay
      PanelRoute.tsx        # /#/panel
    styles/
      overlay.css
      panel.css
    __tests__/
      setup.ts
      WSProvider.test.tsx
      reconnect.test.ts
      AvatarHost.test.tsx
      SpeechBubble.test.tsx
      TaskCard.test.tsx
```

### Wire protocol

`src/ws/protocol.ts` declares the union exactly as `contracts.md` §9 spells
it out. Server-side: `AvatarDirectiveMessage`, `TranscriptPreviewMessage`,
`BubbleTextMessage`, `TaskCardMessage`, `SystemNoticeMessage`. Client-side:
`UserTextMessage`, `PttDownMessage`, `PttUpMessage`, `ModeToggleMessage`,
`TaskCancelMessage`. The `isServerMessage` type-guard is what `WSProvider`
runs on every parsed payload — anything that doesn't pass is dropped.

### `WSProvider`

- Connects on mount via the injected `socketFactory` (defaults to `new
  WebSocket(url)`).
- Decodes every inbound JSON string, narrows via `isServerMessage`, and
  fans out to per-type subscribers registered through `subscribe(type,
  handler)`. `lastMessage` is also exposed for components that just want
  the freshest.
- On `close`, schedules a reconnect through the jittered exponential
  backoff controller. `reset()` is called on the next successful `open`.
- `send(message: ClientMessage)` serialises to JSON and writes; messages
  sent while the socket isn't OPEN are dropped (the user can retry once
  `status` returns to `"open"`).

### Reconnect math

`createReconnectController({initialMs, maxMs, jitterRatio, maxAttempts,
sleep, random})` — pluggable everything. The default ramps 250 ms ->
500 ms -> 1 s -> ... capped at 10 s, ±20 % jitter. Tests prove the
doubling, the cap, the jitter, the reset, and the `maxAttempts` gate.

### Components

- `<AvatarHost />` — reads `useAvatarDirective()`, looks up the runtime
  in the registry (defaulting to `"sprite2d"`), and renders it. Unknown
  runtimes fall back to `PlaceholderRuntime`.
- `<SpeechBubble />` — runs `useBubbleText()`; renders nothing when
  empty; shows a caret while streaming.
- `<TextInput />` — Enter sends `{type:"user.text", text}`. Whitespace
  inputs dropped.
- `<VoiceToggle />` — buttons for `live_wake` / `agent_voice`; sends
  `mode.toggle`; snaps local UI state to server-published
  `config_updated` diffs.
- `<TaskCard />` — feed of every task. Terminal statuses gray out and
  hide the Cancel button. Cancel sends `{type:"task.cancel", handle}`.
- `<ModeIndicator />` — state + WS-status chip.
- `<SettingsPanel />` — `<select>` + button per category; POSTs to
  `/pack/swap` and `/runtime/swap`. `fetcher` is pluggable for tests.

### Registry surface

`runtimes/registry.ts` keeps the M4 export shape (`runtimeRegistry`,
`RuntimeComponent`) and adds:

- `getRuntime(name) -> RuntimeComponent | PlaceholderRuntime`
- `setRuntime(name, component) -> void` so the test suite (and any
  future post-v0.2 modality) can register without touching M7.
- `PlaceholderRuntime` rendered via `React.createElement` so this file
  stays a `.ts` (the M4 import path is `./runtimes/registry`).

### Tauri IPC

`useTauriCommand()` returns typed wrappers for the two commands M8 will
expose (`set_overlay_interactive`, `swap_avatar_runtime`). The
`@tauri-apps/api/core` import is dynamic and guarded by a window-global
check, so the same code runs unmodified in `vite dev` (browser) and
inside the Tauri shell.

### Tests + coverage

`vitest.config.ts` requires ≥80% line/statement coverage on
`src/{ws,components,hooks}` (matches the DoD). All five test files are
hermetic: `MockWebSocket` (no real network), `act()` everywhere a
state update is triggered, no fake timers (the reconnect test uses a
pluggable `sleep`).

Coverage check is local-only (CI will run `pnpm install` first); the
suite ships as-is.

### Out of scope

- Tauri shell (M8). `useTauriCommand` already targets the right command
  surface so the IPC is wired the moment M8 lands.
- Three.js runtime (M9). The registry has `setRuntime` so M9 can plug
  in without amending M7.
- Settings panel "available packs" comes from a hard-coded list today;
  the proper source is the backend `/config` route (debug-gated) — wired
  in a follow-up once a non-debug `/packs` listing endpoint exists.

Closes the M7 task.
