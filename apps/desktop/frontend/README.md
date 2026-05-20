# @openmimicry/desktop-frontend

The M7 React/Vite app. Two routes:

- `/overlay` — transparent host (Tauri overlay window).
- `/panel` — interactive UI (text input, task feed, voice toggles, settings).

Both share one `WSProvider` so the overlay reflects state the panel drives.

## Run it

```bash
# from repo root
pnpm install --frozen-lockfile
pnpm --filter @openmimicry/desktop-frontend dev
# opens http://localhost:5173 — visit /#/panel or /#/overlay
```

The dev server proxies `/ws`, `/api`, and `/static` to
`http://localhost:8000` (M6 backend). Override with
`OPENMIMICRY_BACKEND_HOST=http://your.host:8000`.

## Test

```bash
pnpm --filter @openmimicry/desktop-frontend test
pnpm --filter @openmimicry/desktop-frontend coverage
```

The suite covers `WSProvider` (connect / reconnect / dispatch / send),
`reconnect.ts` (backoff math), `<AvatarHost />` (registry lookup +
projection passthrough + placeholder fallback + runtime swap), 
`<SpeechBubble />` (partial accumulation, listening-state reset), and
`<TaskCard />` (task feed + cancel send).

## Architecture

```
WSProvider (/ws)
  | discriminated union over §9 messages
  v
useAvatarDirective / useBubbleText / useTaskCards / useWS
  |
  v
<AvatarHost />     <SpeechBubble />     <TaskCard />     <SettingsPanel />
  | registry         | hook              | hook            | fetch
  v                                                        v
Sprite2DRuntime (M4) ...                                   POST /pack/swap
ThreeJSRuntime  (M9, post-v0.2)                            POST /runtime/swap
```

`runtimes/registry.ts` exposes `setRuntime(name, component)` so M9 (and
the test suite) can register new runtimes without touching M7.
