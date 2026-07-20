# Licensing and distribution profiles

OpenMimicry's own source code is licensed under the repository's MIT license.
That does not relicense Python/JavaScript/Rust dependencies, model weights,
voice files, character art, or cloud services. Each of those remains subject
to its own terms. This document is release-engineering guidance, not legal
advice.

## Supported profiles

### Commercial profile

`config/profiles/openrouter-commercial.yaml` and
`requirements/profiles/commercial.lock` define the conservative distribution
path. It uses:

- Faster-Whisper for STT;
- the host operating system's speech facility for TTS;
- OpenRouter BYOK or local Ollama for the LLM; and
- memory disabled by default, with standard-library SQLite available when the
  user explicitly enables it.

Piper, Chatterbox, Hindsight, and ElevenLabs are not installed by the
commercial lock. The installed Python dependency closure must pass:

```bash
python scripts/license_audit.py --profile commercial --strict
```

The checked-in lock is a reproducible review input, not a permanent legal
guarantee. Rerun the audit whenever a dependency changes and review the full
license texts before distributing binaries.

### Community Piper profile

Piper is kept for users who intentionally choose the existing free local
voice path. `piper-tts==1.4.2` is isolated under the `piper-community` extra and
is not part of the commercial dependency lock. The current Piper application
code is GPL-3.0 and individual voice model cards can impose different terms.
Do not infer a voice model's license from the Piper package license.

### Community Chatterbox profile

Chatterbox provides free local, consent-gated voice cloning. Its upstream
repository is MIT, but its large ML dependency and model closure is deliberately
opt-in and includes a Git-sourced dependency. It is therefore classified as
community/experimental, not part of the commercial lock. Before distribution,
pin and audit the complete resolved closure and the selected model artifacts.

### Cloud providers

ElevenLabs and OpenRouter integrations are client code only. Users supply
their own tokens and select resources in their own provider accounts. The MIT
license on OpenMimicry does not grant rights to provider services, uploaded
voices, generated audio, or hosted models. The user must accept and comply
with the provider's then-current terms.

### Optional Hindsight memory

The Hindsight client and server source are available under MIT at the time of
this release. Hindsight remains an optional separately installed provider.
Its service deployment, database, embeddings, inference providers, and model
artifacts must be reviewed independently.

## Assets and biometric material

- A character pack's `license` field is mandatory evidence, not automatic
  legal clearance. Commercial mode rejects unknown, GPL/AGPL,
  non-commercial/research-only, and CC-BY-NC labels by default.
- Voice cloning is permitted by the application only after a consent record
  is supplied. The record does not prove that consent is legally sufficient.
- Reference recordings are biometric/personal data in many jurisdictions.
  Keep them private, collect only what is needed, and provide deletion.
- Generated or downloaded model/voice artifacts are not covered by the
  repository's MIT license unless their own license explicitly says so.

## Release checklist

1. Build from the intended named profile in a clean environment.
2. Run the strict installed-closure audit and retain its JSON output.
3. Review `THIRD_PARTY_NOTICES.md` and every bundled license file/model card.
4. Confirm no community extras or unapproved assets entered the commercial
   bundle.
5. Record cloud-provider terms and the date they were reviewed.
6. Have qualified counsel review the actual product, target markets, and
   distribution method before commercial release.

