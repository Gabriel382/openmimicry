# OpenMimicry

**Open embodied avatar interfaces for LLMs and agentic systems.**

OpenMimicry is a local-first platform for running lightweight desktop avatars connected to interchangeable AI backends such as Ollama and future agentic systems.

## Install profiles

- `basic` — simple 2D + VRM + backend adapter + desktop overlay
- `extended` — `basic` + Live2D + voice + extra tools
- `studio` — `extended` + Unity state studio
- `full` — everything

## Quickstart

```bash
make help
make install PROFILE=basic
make run
```

## Project structure

- `core/` — shared runtime logic
- `backends/` — backend adapters
- `avatar/` — avatar runtimes and state logic
- `profiles/` — install profile definitions
- `apps/` — app entrypoints
- `packs/` — optional add-ons
- `scripts/` — helper scripts

See `ROADMAP.md` for milestone planning.
