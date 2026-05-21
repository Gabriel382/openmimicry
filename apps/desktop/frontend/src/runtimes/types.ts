/**
 * Shared shape every avatar-runtime React component exposes.
 *
 * Per the M7 brief, each runtime component subscribes to the current
 * `avatar.directive` via `useAvatarDirective` and renders it. The
 * registry mounts the component without passing runtime-specific props;
 * any extras a runtime needs come from its own state hooks.
 */

import type { ComponentType } from "react";

export interface AvatarRuntimeProps {
  /** Optional className for layout overrides. */
  className?: string;
  /** Optional runtime-specific config (mirrors `avatar.runtimes.<name>`). */
  runtimeConfig?: Record<string, unknown>;
}

export type AvatarRuntimeComponent = ComponentType<AvatarRuntimeProps>;
