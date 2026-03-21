# OpenMimicry

OpenMimicry is a local-first embodied interface layer for LLMs and agentic systems.

## Milestone 3 highlights

- Ollama backend adapter
- common backend router with fallback to mock backend
- chat and streaming support
- model selection from runtime config
- backend health checks and direct Ollama connection test
- runtime event logs and active backend debug output

## Commands

```bash
make install PROFILE=basic
make ollama-test PROFILE=basic
make health PROFILE=basic
make run PROFILE=basic
```

## Notes

The Ollama adapter uses the official Ollama local HTTP API with `/api/chat` for chat and `/api/tags` for model discovery/health checks. Local access does not require authentication in the default local setup. citeturn872330search0turn872330search2turn872330search4
