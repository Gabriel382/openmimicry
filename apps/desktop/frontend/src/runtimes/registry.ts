/**
 * Avatar runtime registry.
 *
 * Maps a runtime id (the value of `runtime` on the `avatar.directive`
 * wire message) to a React component that renders that modality. Each
 * modality (Sprite2D today; Three.js, Live3D, Unity, External later)
 * adds itself here.
 *
 * `getRuntime(name)` returns the registered component or
 * `PlaceholderRuntime` for unknown ids. `setRuntime(name, component)`
 * is exposed so tests can register a transient `MockRuntime`.
 *
 * History
 * -------
 * - M4 created this file with only `runtimeRegistry`.
 * - M7 extended it with `getRuntime`, `setRuntime`, `PlaceholderRuntime`.
 *
 * The placeholder uses `React.createElement` rather than JSX so this
 * file can remain a `.ts` (the M4 import path is `./runtimes/registry`).
 */

import { createElement, type ComponentType } from "react";

import { Sprite2DRuntime } from "./sprite2d";
import type { Sprite2DRuntimeProps } from "./sprite2d";

// Each entry is a component whose props include at least a `projection`
// field; modalities are free to extend their own props.
export type RuntimeComponent = ComponentType<{ projection?: unknown }>;

/**
 * Fallback for unknown runtime ids. Visible enough to debug from.
 * Authored with `createElement` to keep `registry.ts` JSX-free.
 */
export const PlaceholderRuntime: RuntimeComponent = ({ projection }) => {
  const stateLabel =
    projection &&
    typeof projection === "object" &&
    "directive" in (projection as Record<string, unknown>)
      ? String(
          (projection as { directive?: { state?: unknown } }).directive?.state ??
            "?",
        )
      : "?";
  return createElement(
    "div",
    {
      role: "status",
      "aria-label": "placeholder avatar runtime",
      style: {
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        width: "100%",
        height: "100%",
        color: "rgba(255,255,255,0.5)",
        fontFamily: "monospace",
      },
    },
    `runtime not registered (state=${stateLabel})`,
  );
};

export const runtimeRegistry: Record<string, RuntimeComponent> = {
  sprite2d: Sprite2DRuntime as unknown as RuntimeComponent,
  // future:
  // threejs: ThreeJSRuntime,
  // live3d: Live3DRuntime,
  // unity:   UnityRuntime,
  // external: ExternalRuntime,
};

/** Register a runtime component at runtime (tests, lazy-loaded modalities). */
export function setRuntime(name: string, component: RuntimeComponent): void {
  runtimeRegistry[name] = component;
}

/** Look up by name; falls back to `PlaceholderRuntime` for unknown runtimes. */
export function getRuntime(name: string): RuntimeComponent {
  return runtimeRegistry[name] ?? PlaceholderRuntime;
}

export type { Sprite2DRuntimeProps };
