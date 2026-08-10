# OpenMimicry v1.9.1 release notes

OpenMimicry v1.9.1 is a stabilization release for persistent companions,
multilingual voice, Three.js/VRM characters, deterministic desktop tools, and
Claude Code delegation. It is configuration-compatible with v1.9.0.

## What changed

### One identity, one place

Assistant name and aliases live only under **Personality**. Saving them updates
the system prompt identity, live wake recognition, companion state, and exported
profile. The duplicate wake-name and recognition-alias controls were removed
from **Voice**. Existing v1.9.0 wake settings remain readable and are migrated
when personality or a companion is next applied.

### Language changes no longer freeze the dashboard

Input/output language accepts `auto`, English, French, Spanish, and Brazilian
Portuguese (`pt-BR`). A change returns immediately and exposes preparation
progress while the STT model and standard local voice are downloaded or warmed.
The active runtime changes only after preparation succeeds.

The standard isolated Piper path selects a language-matched voice, including
`pt_BR-faber-medium` for Brazilian Portuguese. A custom/cloned voice is retained
instead; its multilingual quality depends on that provider/model and reference.

### Companion voice activation is deterministic

Activating a companion applies its complete saved state as one operation:
character pack/runtime, transform, animation settings, name/aliases,
personality, and bundled voice. A bundled companion voice takes precedence over
a stale global profile with the same ID. The dashboard selector reflects the
voice that is actually active.

Private companions and imported character packs now have **Download** and
**Remove** actions. Bundled defaults cannot be removed.

### VRM controls are honest and usable

Three.js rotation now supports ±360°. Legacy Torikinoko and MINIUS private
imports default to a front-facing 180° Y rotation, while saved transforms remain
authoritative. The dashboard discovers embedded animation clips and provides a
selector for each OpenMimicry lifecycle/gesture alias plus an auto-map action.
If a VRM contains no embedded animation clips, the UI says so; importing a VRM
does not invent animations that are absent from the file.

Creator archives and restricted model bytes are not included in this release.
Users may import their own lawfully obtained archives locally.

### Tools and Claude are observable

The built-in alarm recognizes forms such as `Set an alarm to 17h!` as well as
common Portuguese, Spanish, and French variants. Routing decisions, policy
denials, fallthrough, and successful scheduling are logged. The built-in alarm
is OpenMimicry's durable notification alarm; it does not mutate the operating
system's Clock application.

Claude delegation recognizes `ask claude` anywhere in an accepted utterance,
including after the wake name. It starts the task in the background, waits for
acknowledgement audio readiness, then presents text and voice together. The
companion remains usable while Claude runs, and completion appears through the
existing durable task notification path.

## Upgrade

1. Stop backend and desktop processes.
2. Replace the source tree or merge the v1.9.1 changes.
3. Run the normal project installation command; no specialized launcher is
   introduced.
4. Start the existing voice/backend launcher and desktop launcher.
5. Open Settings and apply the intended companion once if migrating legacy
   split wake/voice state.

See `MIGRATION-v1.9.1.md` for detailed behavior and rollback guidance.

## Known boundaries

- First use of a language/model can require a download; progress is visible and
  the old runtime stays active until the new one is ready.
- Voice cloning and multilingual fidelity remain provider/model dependent.
- VRM lifecycle animation mapping requires clips embedded in the selected VRM.
- Physical microphone, GPU, speaker, browser, OS application, and Claude CLI
  behavior must ultimately be exercised on the target machine.
