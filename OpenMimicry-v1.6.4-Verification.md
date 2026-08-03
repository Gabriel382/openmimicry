# OpenMimicry v1.6.4 verification record

## Scope

This record covers the Perth constructor validation/repair, fail-closed worker
boundary, release consistency, and packaging checks. Hardware synthesis must
still be executed on a Chatterbox-capable target using
`docs/V1.6.4_CHATTERBOX_TESTING.md`.

## Executed in the build workspace

- Python compilation passed for the worker, installer, and voice tests.
- Targeted dependency-free regression checks passed for:
  - replacing a `None` Perth export with the real directly imported class;
  - surfacing the hidden direct-import exception;
  - rejecting a runtime whose Perth constructor is non-callable;
  - preserving a valid CUDA 11.8 Torch triplet;
  - the immutable Perth commit and `--no-deps` repair contract;
  - v1.6.4 preflight-marker invalidation.
- Version consistency passed across 27 Python, Node, Rust, Tauri, backend, and
  package manifests at `1.6.4`.

## Environment limitation

The build container does not contain Chatterbox/Torch audio hardware or the
project's full test dependencies, and policy prevented downloading pytest.
Therefore the real model download, GPU load, watermark construction, and three
turn audio acceptance are explicitly pending on the target Windows machine.
The source does not claim those target-hardware checks were run here.

## Required target result

The target is accepted only when the runtime report contains
`perth_watermarker_callable: true`, worker preflight emits `type: ready`, and
three consecutive cloned-voice turns complete.
