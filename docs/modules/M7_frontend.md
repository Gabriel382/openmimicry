# Module M7: `apps/desktop/frontend`

## Goal (1 line)

Ship the React/Vite application with two routes — `/overlay` (transparent avatar host) and `/panel` (interactive UI) — a WebSocket client that consumes the frontend wire protocol, a runtime-adapter registry, and the speech-bubble + text-input + voice-control + task-card components.

## Scope and non-scope

**In scope.**

- Vite project with the existing scaffolding kept where useful and cleaned up.
- **pnpm 11.x is mandatory.** `.npmrc` enables `minimum-release-age=14`, `block-exotic-subdeps=true`, `ignore-scripts=true`, plus `engine-strict=true`. See `SECURITY.md` §"Supply-chain posture". Do not introduce `package-lock.json` or `yarn.lock`; CI rejects them.
- React Router with two top-level routes: `/overlay` and `/panel`.
- `WSProvider` context wrapping a connection to `/ws` with auto-reconnect, exponential backoff, and a typed message stream (mapping each `type` to a TypeScript discriminated union).
- `runtimes/registry.ts` mapping `"sprite2d" → Sprite2DRuntime`, `"threejs" → ThreeJSRuntime` (post-v0.2), etc. Each runtime is owned by its modality module (M4 ships Sprite2D, M9 ships Three.js).
- `<AvatarHost />` component on `/overlay` that reads the registry and mounts the active runtime.
- `<SpeechBubble />`, `<TextInput />`, `<VoiceToggle />`, `<TaskCard />`, `<ModeIndicator />` components.
- `<SettingsPanel />` on `/panel` with controls for live wake / agent voice / pack swap / runtime swap.
- Tauri IPC client for the Rust-side commands provided by M8 (`set_overlay_interactive`, `swap_avatar_runtime`).

**Non-scope.**

- The Rust/Tauri shell itself (M8).
- The actual rendering code for any modality — those live in their own module's frontend folder (`apps/desktop/frontend/src/runtimes/<modality>/`).
- The backend.

## Inputs (immutable, from contracts.md)

- The frontend wire protocol from `contracts.md` §9 (both inbound and outbound shapes).
- `AvatarDirective` shape (consumed as JSON via `avatar.directive` messages).
- The list of supported runtimes (matches the `avatar.runtime` enum in [`../configuration.md`](../configuration.md)).

## Outputs (this module owns)

```text
apps/desktop/frontend/
  package.json                    # cleaned
  vite.config.ts
  tsconfig.json
  index.html
  src/
    main.tsx
    App.tsx                       # Router setup
    routes/
      OverlayRoute.tsx            # /overlay
      PanelRoute.tsx              # /panel
    ws/
      WSProvider.tsx              # React context
      protocol.ts                 # TypeScript types for the wire protocol
      reconnect.ts                # auto-reconnect logic
    runtimes/
      registry.ts                 # exports { sprite2d, ... }
      types.ts                    # AvatarRuntimeProps shared interface
      # NOTE: per-runtime folders (sprite2d/, threejs/, ...) live here but are
      # owned by their modality module (M4 owns sprite2d/, M9 owns threejs/, ...).
    components/
      AvatarHost.tsx
      SpeechBubble.tsx
      TextInput.tsx
      VoiceToggle.tsx
      TaskCard.tsx
      ModeIndicator.tsx
      SettingsPanel.tsx
    hooks/
      useTauriCommand.ts
      useWS.ts
      useAvatarDirective.ts
      useBubbleText.ts
      useTaskCards.ts
    styles/
      overlay.css
      panel.css
    __tests__/
      WSProvider.test.tsx
      AvatarHost.test.tsx
      SpeechBubble.test.tsx
      TaskCard.test.tsx
      reconnect.test.ts
```

## Mock implementations this module provides

None for Python. For the frontend, `src/ws/mockSocket.ts` exposes a `MockWebSocket` that Vitest tests use in place of the real WS. M7's `WSProvider` accepts an optional `socket: WebSocketLike` prop for injection.

## Test surface

- **Unit (Vitest).** `WSProvider` connects, reconnects with backoff after disconnect, and exposes a typed `useWS()` hook.
- **Unit.** `<SpeechBubble>` shows incremental text on `bubble.text` messages and clears on a new `avatar.directive` with `state="listening"`.
- **Unit.** `<AvatarHost>` looks up the active runtime in `registry` and mounts the component; falls back to a placeholder for unknown runtimes.
- **Unit.** `<TaskCard>` updates from `task.card` messages; clicking cancel sends `{ type: "task.cancel", handle: { ... } }` (outbound additive, document in `contracts.md` §9 amendment).
- **Unit.** Reconnect with jittered exponential backoff bounded by `cfg.maxBackoffMs`.

## Step-by-step plan (atomic, numbered)

1. Audit existing `frontend/` from the prototype. Move/refactor it into `apps/desktop/frontend/`. Update `package.json`: name `@openmimicry/desktop-frontend`, TypeScript strict mode on, scripts `dev`, `build`, `lint`, `typecheck`, `test`, `test:ui`.
2. Update `vite.config.ts` to expose two routes via React Router; configure a dev proxy for `/ws` and `/api` to `http://localhost:8000`.
3. Implement `ws/protocol.ts` with TypeScript types matching `contracts.md` §9 exactly. Use a discriminated union on `type`.
4. Implement `ws/reconnect.ts`: exponential backoff with jitter, optional max retries, optional `onOpen`/`onClose` callbacks.
5. Implement `ws/WSProvider.tsx` providing `{ send, lastMessage, status }` plus a per-message-type subscription API. Inject the socket factory for test injectability.
6. Implement `hooks/useWS.ts`, `useAvatarDirective.ts` (returns the latest `AvatarDirective`), `useBubbleText.ts` (accumulates `bubble.text`), `useTaskCards.ts` (keeps a `Map<handle.id, TaskUpdate>`).
7. Implement `runtimes/types.ts` defining `AvatarRuntimeProps = { runtimeConfig: object }` plus the contract that each runtime component subscribes to `avatar.directive` via `useAvatarDirective`. Implement `runtimes/registry.ts` exporting `{ sprite2d: Sprite2DRuntime }` initially (M4 supplies the component) and a function `getRuntime(name)` with a fallback `<PlaceholderRuntime/>`.
8. Implement `components/AvatarHost.tsx`. Reads `cfg.avatar.runtime` (delivered via the initial `system.notice` config dump or a `/config` GET on startup), looks up in registry, mounts the component.
9. Implement `components/SpeechBubble.tsx`. Subscribes to `bubble.text`; clears on `avatar.directive` listening.
10. Implement `components/TextInput.tsx`. On Enter, `send({ type: "user.text", text })`.
11. Implement `components/VoiceToggle.tsx`. Buttons for live-wake on/off, agent-voice on/off; sends `mode.toggle`.
12. Implement `components/TaskCard.tsx`. Subscribes to task cards; shows status, progress, log tail; cancel button.
13. Implement `components/SettingsPanel.tsx`. Drop-downs for pack and runtime; calls `/pack/swap` and `/runtime/swap` over HTTP.
14. Implement `routes/OverlayRoute.tsx` — full-bleed transparent, hosts `<AvatarHost>` + `<SpeechBubble>`. No text input here.
15. Implement `routes/PanelRoute.tsx` — text input, task cards, settings, voice toggles, mode indicator.
16. Implement `hooks/useTauriCommand.ts` wrapping `@tauri-apps/api/core::invoke`. Provides typed wrappers for the Tauri commands M8 exposes.
17. Write Vitest tests with `@testing-library/react` and a `MockWebSocket`.
18. Add `apps/desktop/frontend/README.md`.
19. Update `CHANGELOG.md`.
20. `make ci`. Open PR `feat(desktop-frontend): M7 — overlay/panel routes, WS client, runtime registry`.

## Definition of done (checklist)

- [ ] `pnpm run dev --prefix apps/desktop/frontend` serves `/overlay` and `/panel`.
- [ ] `pnpm run typecheck` clean.
- [ ] `pnpm run lint` clean.
- [ ] All Vitest tests pass with ≥ 80% coverage on `src/ws`, `src/components`, `src/hooks`.
- [ ] `<AvatarHost>` swaps between two registered runtimes (Sprite2D and a `MockRuntime` shipped only in tests) via the registry.
- [ ] WS auto-reconnects within 5s after a forced disconnect (asserted by test).
- [ ] Text submission round-trips through the `MockWebSocket`.
- [ ] `CHANGELOG.md` entry.

## Recommended LLM brief (copy-pasteable prompt)

> You are implementing **Module M7 (`apps/desktop/frontend`)** of OpenMimicry.
>
> Read in order:
>
> 1. `docs/contracts.md` §9 — the WebSocket wire protocol. This is the contract.
> 2. `docs/modules/M7_frontend.md` — this brief.
> 3. `docs/architecture.md` §9 — process and window topology.
> 4. `docs/desktop_overlay.md` §6 — what's pluggable about the renderer mount.
>
> Implement the 20-step plan. Constraints:
>
> - You do **not** implement Sprite2D, Three.js, or any modality renderer. Those live under `apps/desktop/frontend/src/runtimes/<modality>/` and are owned by their respective modules (M4, M9, …). Your job is the **registry** that mounts them and the shell components around them.
> - Type the WS messages against `contracts.md` §9 verbatim. A drift between TS and Python types is the most likely source of bugs; the protocol is the truth.
> - The `WSProvider` must accept an injected socket factory so tests can supply a `MockWebSocket`.
> - Strict TypeScript. No `any`, no `as unknown as` escape hatches.
>
> Open the PR titled `feat(desktop-frontend): M7 — overlay/panel routes, WS client, runtime registry` with the Definition-of-done checklist ticked. Do not touch `apps/desktop/src-tauri/` — that's M8.
