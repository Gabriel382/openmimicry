# Milestone 0 — Repo and install foundation

## Goal

Have a repo that installs and runs cleanly with profiles.

## Issues / tasks

* create repo structure
* add `README.md`
* add `LICENSE`
* add `CONTRIBUTING.md`
* add `SECURITY.md`
* add `ROADMAP.md`
* define folder structure for:

  * `core/`
  * `backends/`
  * `avatar/`
  * `profiles/`
  * `apps/`
  * `packs/`
  * `scripts/`
* create Python project config
* create `.env.example`
* create `Makefile`
* add `make help`
* add `make install PROFILE=...`
* add `make run`
* add `make doctor`
* add `make clean`

---

# Milestone 1 — Core config and package system

## Goal

Make the project configurable and profile-based.

## Issues / tasks

* create central config loader
* create profile definition files:

  * `basic`
  * `extended`
  * `studio`
  * `full`
* create package/add-on registry
* create addon manifest format
* create package resolver from selected profile
* make install scripts install only selected dependencies
* add config validation
* add default runtime settings file

---

# Milestone 2 — Backend adapter layer

## Goal

Have one simple backend interface that can later switch between Ollama, OpenAI-compatible, Claude, PicoClaw/OpenClaw, etc.

## Issues / tasks

* define backend base interface
* define backend request/response schema
* define streaming response schema
* define backend status/events
* create mock backend
* create backend router
* create backend config selection
* add backend health check
* add test backend switch command

---

# Milestone 3 — First real LLM connection

## Goal

Connect to one real LLM backend with minimal complexity.

## Issues / tasks

* implement Ollama adapter first
* add chat request support
* add streaming support
* add model selection from config
* add connection test command
* add fallback to mock backend on failure
* add backend logs/events
* expose active backend in UI/debug info

---

# Milestone 4 — Desktop overlay shell

## Goal

Get a transparent desktop window with always-on-top support.

## Issues / tasks

* choose first shell implementation
* create frameless transparent window
* add always-on-top
* add draggable avatar area
* add tray icon or hidden launcher
* add open/close control panel
* add basic event loop between UI and backend
* add cross-platform window config
* add minimal desktop packaging flow

---

# Milestone 5 — Simple 2D avatar runtime

## Goal

First usable avatar on desktop.

## Issues / tasks

* create avatar state model:

  * idle
  * listening
  * thinking
  * speaking
  * happy
  * error
* create simple image-based avatar runtime
* load avatar from folder
* define avatar folder structure
* implement state switching
* connect backend events to avatar states
* add optional speech bubble/text overlay
* add basic idle timer behavior
* create one demo avatar pack

---

# Milestone 6 — 2D avatar config/state mapping

## Goal

Allow easy avatar swapping and reusable state definitions.

## Issues / tasks

* define avatar config file format
* map states to image assets
* support per-state timing/options
* support fallback missing-state behavior
* add avatar pack loader
* add avatar validation command
* add easy avatar switching in config
* add sample second avatar pack

---

# Milestone 7 — VRM runtime

## Goal

Add first practical 3D runtime.

## Issues / tasks

* define VRM runtime module
* load `.vrm` avatar file
* render avatar with transparent background
* add idle animation support
* add blink support
* add simple talk motion
* add state-driven expression switching
* add avatar file hot-swap
* add sample VRM avatar support path
* add VRM runtime toggle in config

---

# Milestone 8 — VRM state mapping

## Goal

Make VRM avatars configurable like 2D ones.

## Issues / tasks

* define VRM state mapping schema
* map avatar states to:

  * expression
  * animation clip
  * gesture
* add default motion fallback
* add animation clip registration
* add runtime state transition rules
* add config validation
* add example VRM state config

---

# Milestone 9 — Basic control panel

## Goal

Give the user an actual usable interface beyond the floating avatar.

## Issues / tasks

* create hidden or separate control panel
* add chat history view
* add backend selector
* add model selector
* add avatar selector
* add logs/events panel
* add runtime status display
* add settings persistence
* add restart/reconnect action

---

# Milestone 10 — Live2D runtime

## Goal

Add lightweight expressive 2D as an optional package.

## Issues / tasks

* create Live2D runtime pack
* load Live2D model
* connect model to transparent overlay
* support idle/listening/thinking/speaking states
* support expression switching
* support motion switching
* add Live2D runtime config
* add runtime selection between simple 2D and Live2D
* add install under `extended` profile only

---

# Milestone 11 — Live2D state mapping

## Goal

Map system states to Live2D motions and expressions.

## Issues / tasks

* define Live2D state config schema
* map states to expression names
* map states to motion names
* define transition rules
* add missing-motion fallback
* add validation tool
* add example Live2D avatar pack

---

# Milestone 12 — Package/add-on commands

## Goal

Let the user install only what they want.

## Issues / tasks

* add `make list-profiles`
* add `make list-packs`
* add `make add PACK=...`
* add `make remove PACK=...`
* add pack dependency resolution
* add pack installation hooks
* add pack uninstall hooks
* add pack metadata display
* add pack compatibility checks

---

# Milestone 13 — Extra backends

## Goal

Make backend swapping real.

## Issues / tasks

* implement OpenAI-compatible adapter
* implement Claude adapter
* implement PicoClaw/OpenClaw adapter
* add backend-specific config schema
* add backend capability discovery
* add runtime backend switching
* add connection test for each backend
* add backend docs/examples

---

# Milestone 14 — Voice package

## Goal

Add practical assistant utility.

## Issues / tasks

* add TTS package
* add STT package
* add microphone input
* add push-to-talk or hotkey
* connect speaking state to avatar
* connect listening state to avatar
* add voice config settings
* keep under `extended` profile

---

# Milestone 15 — Unified avatar state schema

## Goal

One common state system for 2D, Live2D, and VRM.

## Issues / tasks

* define common avatar state schema
* define common avatar event model
* normalize runtime-specific state mappings
* add shared validation
* add migration rules for old configs
* update docs and examples

---

# Milestone 16 — Unity state studio

## Goal

Use Unity as a visual state-mapping studio, not as the first runtime.

## Issues / tasks

* create Unity project
* import VRM/avatar assets
* preview avatar states
* associate state to existing:

  * animation
  * expression
  * pose
* define exportable state map
* export config compatible with main runtime
* add test/example workflow
* document Unity studio installation
* put under `studio` profile

---

# Milestone 17 — Asset exploration and validation tools

## Goal

Make avatar swapping easier and safer.

## Issues / tasks

* add avatar inspector command
* inspect VRM structure
* inspect available expressions
* inspect animation clips
* inspect missing mapped states
* inspect 2D/Live2D pack completeness
* generate validation report
* add `make validate-avatar`

---

# Milestone 18 — Packaging and distribution

## Goal

Make the project easy to use for real users.

## Issues / tasks

* add local packaging flow
* add release build commands
* add portable config structure
* add example packaged profiles
* add install docs per OS
* add basic troubleshooting docs
* add release checklist

---

# Milestone 19 — Final polish for v1

## Goal

Make the project feel like a real flagship repo.

## Issues / tasks

* improve README with screenshots/GIFs
* add demo avatars
* add example configs
* add architecture diagrams
* add profile comparison table
* add backend comparison table
* add avatar runtime comparison table
* add first showcase demo video
* add issue templates / PR template
