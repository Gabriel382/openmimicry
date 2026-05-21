# How to write the OpenMimicry README

The README is the front door. A recruiter reads it in 60 seconds; a contributor reads it in 5 minutes; a user reads it once when they install. Optimise for all three, in that order.

This document is the spec for `README.md`, not the README itself. Use it when you rewrite `README.md` after the migration.

## 1. Above-the-fold (everything visible without scrolling)

- A tight one-sentence pitch.
- A screenshot or short GIF of the avatar talking on a desktop.
- A row of meaningful badges.
- A one-paragraph "what works today" with three bullet links to deeper docs.

Example one-liner:

> **OpenMimicry is a modular avatar interface layer for LLMs, voice systems, and agentic task runtimes.** A 2D sprite, a Three.js VRM, a live 3D model, or a Unity scene — same backend, same event bus, swappable visual frontend.

Pair it with a one-line subtitle that names the *plug points*:

> One core. Pluggable LLM (LiteLLM), STT/TTS (RealtimeSTT/RealtimeTTS), task runtimes (Claude Code, mcp-agent, local shell), and avatar renderers (Sprite2D, Three.js, Unity, external).

## 2. Be honest about status

The README must say what works today and what is planned. Hide neither. A recruiter trusts a `0.x` project that is precise about its boundaries far more than one that overclaims.

Suggested phrasing:

> Status: research preview, v0.2.x. The Sprite2D avatar runtime, text/voice loop (RealtimeSTT + RealtimeTTS), LiteLLM-backed chat, and mcp-agent / Claude Code task delegation are working end-to-end on Windows and Linux. The Three.js / VRM, Live 3D, and Unity bridge modalities are on the roadmap (P9–P11 in `docs/migration.md`).

## 3. Sections, in order

1. **What it is.** Two paragraphs. No marketing voice. Lead with "modular avatar interface layer."
2. **Demo.** GIF + a 60-second YouTube link if it exists. Show at least two modalities side by side (Sprite2D and Three.js) to make the pluggability story visible.
3. **Architecture diagram.** A single high-level picture — modules and arrows — linking to [`architecture.md`](./architecture.md). One image is worth a thousand bullet points here.
4. **Modality progression table.** The narrative arc, in one table:
   ```
   PROFILE      install               avatar             use case
   basic        pip install -e .[basic]   Sprite2D         first-time user, low footprint
   voice        pip install -e .[voice]   Sprite2D + voice hands-free demo
   threejs      pip install -e .[threejs] Three.js / VRM   portfolio screenshots, 3D demos
   live3d       pip install -e .[live3d]  Live 3D          research, education, livestream
   unity        pip install -e .[unity]   Unity (bridge)   game-like companions, XR pilots
   full         pip install -e .[full]    everything       contributors
   ```
   This table is the single most important persuasion device in the README. It says "this is a platform, pick your level."
5. **Quickstart.** Three commands that work from a fresh clone:
   ```
   make doctor
   make install PROFILE=basic
   make dev
   ```
   And how to point the chat path at OpenRouter or Ollama with one env var.
6. **Pick a personality.** A pointer to `characters/` and a one-paragraph "make your own pack" recipe. Link to [`character_packs.md`](./character_packs.md) for Sprite2D and [`avatar_modalities.md`](./avatar_modalities.md) for the 3D/Unity story.
7. **Voice modes.** Half-page summary; link to [`voice_modes.md`](./voice_modes.md).
8. **Task delegation.** Half-page; link to [`task_delegation.md`](./task_delegation.md).
9. **How adapters compose.** Tiny diagram of LLMAdapter / STTAdapter / TTSAdapter / TaskRuntimeAdapter / **AvatarRuntimeAdapter**; link to [`adapters.md`](./adapters.md).
10. **Roadmap.** Pull from `ROADMAP.md`. Just the next 3 milestones. Always show at least one upcoming modality (Three.js, Live 3D, or Unity) so the platform framing stays visible.
11. **Contributing.** Link to `CONTRIBUTING.md` and the "good first issue" label. Call out that *writing a new modality is a great first contribution*: implement `AvatarRuntimeAdapter`, pass the contract test, open a PR.
12. **Known issues.** Honest list: Wayland click-through quirks, mic echo, etc.
13. **License & credits.** Including thanks to LiteLLM, RealtimeSTT, RealtimeTTS, mcp-agent, Three.js, Tauri.

## 4. Anti-patterns to avoid

- **"AGI", "revolutionary", "next-gen".** Pure noise; reviewers learn to skim past projects that lead with them.
- **Long install logs as screenshots.** Use commands.
- **Animated banner GIFs that take 15 seconds to loop.** A 3–5 second loop of the avatar transitioning idle -> listening -> speaking is enough.
- **Promises about features the code does not have.** State the roadmap in `ROADMAP.md`, not the README.
- **Walls of text.** Each section above is ≤ 200 words. The reader can click through to depth in `docs/`.

## 5. Things that punch above their weight

- A clear "Why this exists" paragraph. Two sentences explaining what gap it fills compared to a chat app or a CLI agent. This is the hardest part of the README to write; it's also the section that converts a skim into a star.
- A "designed to be forked" line. Many companion projects are demos; OpenMimicry is meant to host third-party adapters and packs. State that on the README, not just in the architecture doc.
- The **modality progression table** in §3.4 — it converts skimmers because they instantly see what level *they* would land at.
- One screenshot showing the *same* character in two modalities (Sprite2D and Three.js or Sprite2D and Unity). That's the proof, in one image, that the avatar is genuinely pluggable.
- A working install on both Windows and Linux. The README links to CI for proof.
- A `make doctor` command that prints a checklist. Show its output in the README.

## 6. Length target

The rendered README should fit on roughly two screens at desktop resolution. Anything longer goes into `docs/`. The point of the README is to get the reader to either install or click into the architecture, not to be a complete reference.

## 7. Maintenance

- The README is updated in the same PR as any feature change that affects the quickstart.
- The screenshot is regenerated for each major release.
- The badges row is checked at release time; broken badges hurt more than missing badges.
