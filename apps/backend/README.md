# openmimicry-backend

The M6 FastAPI process. Imports every concrete adapter through
`wiring.py` — every other module in this package uses the Protocols
in `openmimicry.core.contracts.*`.

## Run it (mocks-only, zero config)

```bash
# from repo root
make install PROFILE=dev
uvicorn openmimicry_backend.main:app --reload --port 8000
```

That brings up `/health`, `/chat`, `/mode/toggle`, `/pack/swap`,
`/runtime/swap`, `/admin/reload`, `/config`, and the WebSocket at `/ws`.
With the default config (every adapter is a mock), `POST /chat` runs
the mock LLM end-to-end and the WS streams the projected events.

## Run it against a real model

Point at a config file:

```bash
OPENMIMICRY_CONFIG_PATH=./config/dev.yaml \
  uvicorn openmimicry_backend.main:app --port 8000
```

The config schema lives in `docs/configuration.md`; an example with
`llm.adapter: litellm` + `voice.{stt,tts}.adapter: realtime*` covers a
real provider stack.

## Architecture

```
HTTP / WS
   |
   v
routes/* + ws.py        <- Protocol consumers only
   |
   v
wiring.Wiring (frozen)  <- the single assembly point (Protocols)
   |
   v
wiring.py imports concrete: MockLLMAdapter, LiteLLMAdapter,
MockSTTAdapter, RealtimeSTTAdapter, MockTTSAdapter, RealtimeTTSAdapter,
MockAvatarRuntimeAdapter, Sprite2DAvatarAdapter, TaskRouter,
{Mock,LocalShell,ClaudeCode,MCPAgent}TaskRuntimeAdapter.
```

`scripts/check_imports.py` enforces this rule statically; `wiring.py`
is on the allowlist.
