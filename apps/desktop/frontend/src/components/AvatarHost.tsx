/**
 * `<AvatarHost />` — the overlay's avatar root.
 *
 * Reads the most recent `avatar.directive` via `useAvatarDirective`, looks up
 * the runtime in the registry (defaults to `"sprite2d"`), and renders the
 * component, passing the wire message down as `projection`.
 *
 * `<AvatarHost />` itself is dumb. The frame timing, preloading, and the
 * runtime swap invariants live inside the modality components.
 */

import { createElement, useMemo } from "react";

import { useAvatarDirective } from "../hooks/useAvatarDirective";
import { getRuntime } from "../runtimes/registry";

export interface AvatarHostProps {
  /** Optional override; falls back to `directive.runtime ?? "sprite2d"`. */
  defaultRuntime?: string;
  className?: string;
}

export function AvatarHost(props: AvatarHostProps): JSX.Element {
  const directive = useAvatarDirective();
  const runtimeId = useMemo(() => {
    const fromDirective = directive?.runtime;
    if (typeof fromDirective === "string" && fromDirective.length > 0) {
      return fromDirective;
    }
    return props.defaultRuntime ?? "sprite2d";
  }, [directive?.runtime, props.defaultRuntime]);

  const Runtime = getRuntime(runtimeId);

  return (
    <div className={`avatar-host ${props.className ?? ""}`} data-runtime={runtimeId}>
      {createElement(Runtime, { projection: directive ?? undefined })}
    </div>
  );
}
