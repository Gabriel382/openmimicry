# OpenMimicry v1.6.4 release manifest

## Contents

- MIT-licensed OpenMimicry v1.6.4 source with configuration schema v2.
- Permanent detection and targeted repair of Perth's non-callable watermark
  constructor, pinned to the official MIT upstream commit.
- The v1.6.3 unified launcher and non-destructive CUDA selection fixes.
- The v1.6.2 Chatterbox/NumPy 2 dtype compatibility boundary and persistent
  isolated synthesis worker.
- The v1.6.1 memory-settings validation fix and v1.6.0 configuration,
  personality, optional memory, character import, and voice-provider features.
- GitHub issue text, release notes, verification record, and target-hardware
  acceptance procedure for the Perth startup repair.
- Commercial and optional community dependency profiles; optional provider,
  model, and reference-audio terms remain separate.
- The unchanged character template under
  `examples/OpenMimicry-character-template-v1.6.0.zip`.

## Source archive policy

`OpenMimicry-v1.6.4-perth-repair-source.zip` contains this directory at its top
level. It excludes local virtual environments, `node_modules`, build output,
caches, bytecode, egg metadata, Rust targets, logs, databases, and user-secret
overlays. Restore dependencies only from the checked-in manifests and locks.

The source archive checksum is recorded next to the archive in
`OpenMimicry-v1.6.4-SHA256SUMS.txt`; it cannot be embedded inside the archive
without changing the checksum it describes.
