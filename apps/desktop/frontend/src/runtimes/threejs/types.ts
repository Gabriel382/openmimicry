/**
 * Shared types for the Three.js runtime.
 *
 * `CharacterController` is the duck-typed surface that VRM and plain
 * glTF loaders both satisfy. The rest of the runtime (clip-playing,
 * expression setting, gaze targeting) talks to this interface only —
 * no branching on `kind` outside the loaders themselves.
 */

import type { Object3D, Scene } from "three";

export type ExpressionWeights = Record<string, number>;

export interface CharacterLoadOptions {
  url: string;
  /** Optional scene to add the loaded root into. Tests can omit. */
  scene?: Scene;
}

export interface CharacterController {
  /** Loader provenance for diagnostics; rendering doesn't branch on this. */
  kind: "vrm" | "gltf";
  root: Object3D;
  /** Available clip names (read once after load). */
  clipNames: string[];
  setExpression(weights: ExpressionWeights): void;
  playClip(name: string, fadeMs?: number): void;
  currentClip(): string | null;
  setGazeTarget(target: string): void;
  dispose(): void;
}
