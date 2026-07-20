# Third-party notices

OpenMimicry is MIT-licensed. Third-party components retain their own licenses.
This file identifies important direct and optional integrations; the complete
installed Python closure for the commercial profile is recorded by
`requirements/profiles/commercial.lock` and can be inspected with
`scripts/license_audit.py`. Distribution must include the license texts
required by the exact versions and artifacts actually shipped.

| Component | Use | Profile | Upstream license/terms |
|---|---|---|---|
| FastAPI / Starlette / Uvicorn | Local backend | all | MIT / BSD-3-Clause |
| Pydantic | Configuration and transport validation | all | MIT |
| LiteLLM | LLM provider adapter | provider profiles | MIT |
| Faster-Whisper / CTranslate2 | Local STT | voice profiles | MIT |
| sounddevice / PortAudio | Audio capture | voice profiles | MIT / PortAudio license |
| NumPy | Audio arrays | voice profiles | BSD-family |
| React | Desktop UI | desktop | MIT |
| Vite | Frontend build tooling | development/build | MIT |
| Tauri | Native desktop shell | desktop | Apache-2.0 OR MIT |
| Hindsight | Optional memory provider | opt-in | MIT; service/model dependencies separate |
| Chatterbox | Optional free local cloning | community opt-in | MIT upstream; model/dependency artifacts separate |
| Perth | Chatterbox audio watermark | community opt-in | MIT upstream; compatibility source pinned to commit `ce86c49d029f42272c1902eccb675556b9ed2330` |
| Piper | Optional local speech | community opt-in only | GPL-3.0 application; voice model cards vary |
| ElevenLabs | Optional hosted TTS/voice | cloud opt-in | Provider terms; user-owned account/token |
| OpenRouter | Optional hosted LLM gateway | provider opt-in | Provider and selected-model terms |
| Ollama | Optional local model service | provider opt-in | Service and selected-model licenses vary |

The commercial Python audit for v1.6.0 allowed permissive licenses and
MPL-2.0 and found no missing or denied metadata in the clean reviewed
environment. That result applies only to the audited resolution; metadata can
change between versions and package indexes can replace artifacts.

See `docs/licensing.md` for profile boundaries and the release checklist.
