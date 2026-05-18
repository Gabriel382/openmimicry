/**
 * Avatar runtime registry.
 *
 * Maps a runtime id (the value of `runtime` on the `avatar.directive` wire
 * message) to a React component that renders that modality. Each modality
 * (Sprite2D today; Three.js, Live3D, Unity, External later) adds itself
 * here.
 *
 * The frontend's avatar root component looks up the active runtime via
 * `runtimeRegistry[currentRuntimeId] ?? FallbackRuntime`. M7 owns that
 * provider; M4 only ships the entry.
 */

import type { ComponentType } from "react";

import { Sprite2DRuntime } from "./sprite2d";
import type { Sprite2DRuntimeProps } from "./sprite2d";

// Each entry is a component whose props include at least a `projection`
// field; modalities are free to extend their own props.
export type RuntimeComponent = ComponentType<{ projection?: unknown }>;

export const runtimeRegistry: Record<string, RuntimeComponent> = {
  sprite2d: Sprite2DRuntime as unknown as RuntimeComponent,
  // future:
  // threejs: ThreeJSRuntime,
  // live3d: Live3DRuntime,
  // unity:   UnityRuntime,
  // external: ExternalRuntime,
};

export type { Sprite2DRuntimeProps };
