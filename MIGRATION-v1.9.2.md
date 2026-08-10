# Migrating to OpenMimicry v1.9.2

## Upgrade

1. Stop the desktop and backend.
2. Replace the source tree with v1.9.2 or merge these changes into the current
   development branch.
3. Run the same installation command/profile already used for v1.9.1.
4. Start the backend with the ordinary launcher, then start the desktop.
5. Open Settings once and verify the saved companion, voice, wake toggle, and
   3D transform.

No configuration schema bump, voice re-import, or specialized Chatterbox script
is required.

## Behavior changes

- An unsaved 3D transform now starts at Y rotation 180°. Existing explicit
  per-character rotations are preserved.
- Creator-specific local-import presets no longer exist. Use the generic custom
  VRM form and enter the asset's actual author and license terms.
- A clipless VRM uses procedural body motion. Facial expressions discovered in
  VRM 0/1 metadata continue to operate independently of skeletal clips.
- Switching wake/continuous listening off is final until the user explicitly
  turns a passive mode on again.
- A failed Chatterbox synthesis process is replaced automatically on the next
  turn.

## Rollback

Stop both processes and restore the v1.9.1 source. User data is not rewritten by
this migration. Note that v1.9.1 will again show only skeletal clips and retains
the stale-listener and tokenizer failure risks fixed here.
