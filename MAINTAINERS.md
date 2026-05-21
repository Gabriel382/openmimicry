# Maintainers

This file documents who owns what in OpenMimicry, how reviews flow, and how decisions get made. It is the human side of the contract that [`docs/parallel_execution.md`](./docs/parallel_execution.md) and [`docs/contracts.md`](./docs/contracts.md) define on the code side.

Owners are listed by their GitHub handle. A module can have one or more owners. The first owner listed is the **primary owner** and is the default reviewer.

## Module ownership

| Module | Primary owner | Co-owners | Notes |
|---|---|---|---|
| Phase 0 — contracts | @ghenrique | — | Two-person rule: any change requires a second approver. |
| MX — tooling | @ghenrique | — | Cross-cutting. CI, releases, lints. |
| M0 — `openmimicry-core` | @ghenrique | — | EventBus, config, runtime store, logging. |
| M1 — `openmimicry-llm` | @ghenrique | — | LiteLLM adapter, router, mock. |
| M2 — `openmimicry-voice` | @ghenrique | — | RealtimeSTT/RealtimeTTS, SpeechController. |
| M3 — `openmimicry-avatar` (core) | @ghenrique | — | Pack loader, director, orchestrator. |
| M4 — Sprite2D adapter | @ghenrique | — | First avatar modality. |
| M5 — `openmimicry-tasks` | @ghenrique | — | TaskRouter, mcp-agent, Claude Code, local shell. |
| M6 — `apps/backend` | @ghenrique | — | FastAPI process, wiring, WebSocket projection. |
| M7 — `apps/desktop/frontend` | @ghenrique | — | React/Vite, overlay/panel routes. |
| M8 — `apps/desktop/src-tauri` | @ghenrique | — | Tauri shell, windows, hotkeys, tray. |
| M9 — Three.js adapter | TBD | — | Open for community contribution. |
| M10 — Live 3D adapter | TBD | — | Open for community contribution. |
| M11 — Unity bridge | TBD | — | Open for community contribution; requires Unity expertise. |
| M12 — External renderer | TBD | — | Open for community contribution. |
| Character packs | @ghenrique | — | Octomimic, mimic_blue. New packs welcome. |
| Documentation | @ghenrique | — | Architecture, adapter docs, migration plan. |
| Security | @ghenrique | — | See [`SECURITY.md`](./SECURITY.md). |

Until a second human maintainer signs on, "two-person rule" reviews on Phase 0 / contract amendments can be satisfied by a documented LLM review (Claude or another model) attached to the PR. The intent is "fresh eyes", not bureaucracy.

## Review rotation

OpenMimicry has one tier of reviewers: **module owners**. Every PR is reviewed by at least one owner of the modules it touches.

Rules:

1. The PR author **may not** be the sole approver. A second human approval is required to merge.
2. PRs that touch `docs/contracts.md`, `packages/openmimicry-core/src/openmimicry/core/contracts/`, or `packages/openmimicry-core/src/openmimicry/core/schemas/` require **two** approving reviews. This is the "two-person rule" for the immutable surface.
3. PRs labelled `breaking` require approval from the primary Phase 0 owner.
4. PRs that touch CI workflows or release pipelines require MX-owner approval.
5. Documentation-only PRs may be self-merged by any owner after 24 hours if no review has been requested.

Review SLA targets (best effort, not contractual):

- First response: 2 working days.
- Full review: 5 working days.
- Security fixes: 24 hours.

If you need urgent attention, ping the primary owner directly via `@mention` in the PR.

## Becoming a maintainer

New maintainers come in through one of three paths:

1. **Merge three substantive PRs** in a module area. The current primary owner can nominate you as a co-owner. Co-owner status grants review rights for that module.
2. **Own a new module** end-to-end (e.g. M9, M10, M11, M12). Implementing a module from a brief in `docs/modules/` plus passing the contract test plus shipping the docs makes you the primary owner of that module by default.
3. **Maintain a character pack** that ships in `characters/` for at least one minor release. Pack maintainers have review rights on `characters/` and on the pack loader / validator.

Removal is rare and not automatic. If a maintainer is inactive for two minor releases, the primary repo owner may move their entry to "alumni" (still listed, but no longer on the default reviewer rotation). Maintainers can step back at any time.

## Decision-making

Most decisions are made by the relevant module owner via PR review. For decisions that affect multiple modules or the public contract:

1. **Open an issue** labelled `rfc:` describing the problem and at least two options.
2. **Tag the affected module owners.** The discussion happens in the issue.
3. **Reach rough consensus** within 7 days. If consensus cannot be reached, the primary repo owner decides and documents the reasoning in the issue.
4. **Convert the decision to a contracts amendment PR** if it changes anything in `docs/contracts.md`.

The bar to amend the immutable surface is deliberately high. Read [`docs/contracts.md`](./docs/contracts.md) §11 for the change protocol. Most "I need a new field" requests are better solved by additive Stable extensions, not by changing Frozen surfaces.

## Escalation

If a PR is stuck or a disagreement is hot:

- **Architectural** disagreements: open an `rfc:` issue. The primary repo owner is the tiebreaker.
- **Security** concerns: follow [`SECURITY.md`](./SECURITY.md). Do not open a public issue.
- **Code of conduct** concerns: contact the primary repo owner privately. See [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md) for full reporting guidelines.

## What we ask of maintainers

- Honour the [Code of Conduct](./CODE_OF_CONDUCT.md).
- Honour [Conventional Commits](https://www.conventionalcommits.org/) in commit messages.
- Honour the parallel-execution rules in [`docs/parallel_execution.md`](./docs/parallel_execution.md) §3 — no cross-module imports, no unilateral contract changes, no bundled PRs.
- When you review, look at the **Definition of done** checklist in the module brief. If the PR doesn't satisfy every item, request changes.
- When you ship, update `CHANGELOG.md` under `## [Unreleased]`.

## Hall of acknowledgement

Real people and real tools that made OpenMimicry possible. Listed in no particular order:

- The maintainers of [LiteLLM](https://github.com/BerriAI/litellm), [RealtimeSTT](https://github.com/KoljaB/RealtimeSTT), [RealtimeTTS](https://github.com/KoljaB/RealtimeTTS), and [mcp-agent](https://github.com/lastmile-ai/mcp-agent).
- The [Tauri](https://tauri.app/) team for keeping desktop bundles small and honest.
- The [Three.js](https://threejs.org/) and [`@pixiv/three-vrm`](https://github.com/pixiv/three-vrm) communities.
- Everyone who has filed a "good first issue" PR.

---

This file is reviewed at every minor release. If your name should be on it and isn't, open a PR.
