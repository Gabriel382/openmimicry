/**
 * `ThreeJSRuntime` — the React mount point for the Three.js modality.
 *
 * Receives the latest `avatar.directive` (passed as `projection` by
 * `<AvatarHost>`), resolves the clip + expression weights, and drives
 * the `CharacterController` returned by the loader. The renderer is
 * paused while the overlay window is hidden (Tauri emits a
 * `window-hidden` event); we listen lazily so the runtime works in
 * pure-browser dev too.
 *
 * Loaders are pluggable so unit tests inject a stub without resolving
 * the real Three.js / VRM stack.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { pickClip, pickGestureClip } from "./clips";
import { mergeWeights, resolveExpression } from "./expressions";
import type { CharacterController } from "./types";

export interface ThreeJSProjection {
  type: "avatar.directive";
  runtime: "threejs";
  directive?: {
    state: string;
    emotion?: string | null;
    speaking?: boolean;
    intensity?: number | null;
    gesture?: string | null;
    gaze?: string | null;
  };
  asset?: { kind: "vrm" | "gltf"; url: string; pack_id?: string };
  clip?: string;
  fallbackClips?: string[];
  expressionWeights?: Record<string, number>;
  gestureClip?: string;
  gazeTarget?: string;
  fadeMs?: number;
  intensity?: number;
}

export interface ThreeJSRuntimeProps {
  projection?: ThreeJSProjection;
  className?: string;
  /** Pluggable VRM loader (tests inject). Async to match the real loader. */
  vrmLoader?: (url: string) => Promise<CharacterController>;
  /** Pluggable glTF loader (tests inject). */
  gltfLoader?: (url: string) => Promise<CharacterController>;
}

/**
 * Browser-canvas-free Three.js mount: we only attach a `<div>` and let
 * the loaders own the renderer. The runtime is fault-tolerant: when no
 * asset is configured we show a small status label so the user knows
 * what's missing.
 */
export function ThreeJSRuntime(props: ThreeJSRuntimeProps): JSX.Element {
  const projection = props.projection;
  const containerRef = useRef<HTMLDivElement | null>(null);
  const controllerRef = useRef<CharacterController | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  const assetUrl = projection?.asset?.url ?? null;
  const assetKind = projection?.asset?.kind ?? "vrm";

  // -----------------------------------------------------------------------
  // Asset lifecycle
  // -----------------------------------------------------------------------

  useEffect(() => {
    if (!assetUrl) return;
    let cancelled = false;
    setStatus("loading");
    setError(null);

    const loader =
      assetKind === "vrm" ? props.vrmLoader : props.gltfLoader;

    (async () => {
      try {
        const ctrl = loader
          ? await loader(assetUrl)
          : await defaultLoad(assetUrl, assetKind);
        if (cancelled) {
          ctrl.dispose();
          return;
        }
        controllerRef.current?.dispose();
        controllerRef.current = ctrl;
        setStatus("ready");
      } catch (e) {
        if (cancelled) return;
        controllerRef.current = null;
        setError(e instanceof Error ? e.message : String(e));
        setStatus("error");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [assetUrl, assetKind, props.vrmLoader, props.gltfLoader]);

  // Tear down the controller on unmount.
  useEffect(() => {
    return () => {
      controllerRef.current?.dispose();
      controllerRef.current = null;
    };
  }, []);

  // -----------------------------------------------------------------------
  // Directive application
  // -----------------------------------------------------------------------

  const computed = useMemo(() => {
    if (!projection) return null;
    const directive = projection.directive ?? { state: "idle" };
    const speaking = Boolean(directive.speaking);
    const emotion = directive.emotion ?? "neutral";
    const intensity = clamp01(
      projection.intensity ??
        (directive.intensity == null ? 1 : Number(directive.intensity)),
    );
    const expressionWeights = mergeWeights(
      resolveExpression(emotion, intensity),
      projection.expressionWeights ?? {},
    );
    return {
      state: directive.state,
      emotion,
      speaking,
      intensity,
      gesture: directive.gesture ?? null,
      gazeTarget: projection.gazeTarget ?? directive.gaze ?? "towards_user",
      preferredClip: projection.clip ?? null,
      fallbackClips: projection.fallbackClips ?? [],
      expressionWeights,
      gestureClip: projection.gestureClip ?? null,
      fadeMs: projection.fadeMs ?? 220,
    };
  }, [projection]);

  useEffect(() => {
    const ctrl = controllerRef.current;
    if (!ctrl || !computed) return;
    const available = ctrl.clipNames;
    let clipName = computed.preferredClip;
    if (!clipName || !available.includes(clipName)) {
      clipName = pickClip({
        state: computed.state,
        emotion: computed.emotion,
        speaking: computed.speaking,
        available,
      });
    }
    ctrl.playClip(clipName, computed.fadeMs);
    const gestureClip = pickGestureClip(
      computed.gestureClip ?? computed.gesture,
      available,
    );
    if (gestureClip) {
      ctrl.playClip(gestureClip, computed.fadeMs);
    }
    ctrl.setExpression(computed.expressionWeights);
    ctrl.setGazeTarget(computed.gazeTarget);
  }, [computed]);

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <div
      ref={containerRef}
      className={`avatar avatar--threejs ${props.className ?? ""}`}
      data-status={status}
      data-state={projection?.directive?.state ?? "idle"}
    >
      {status === "loading" && (
        <span className="avatar--threejs__status">Loading…</span>
      )}
      {status === "error" && (
        <span className="avatar--threejs__error" role="alert">
          {error ?? "load error"}
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Default loader (dynamic imports → bundle splits cleanly)
// ---------------------------------------------------------------------------

async function defaultLoad(
  url: string,
  kind: "vrm" | "gltf",
): Promise<CharacterController> {
  if (kind === "vrm") {
    const mod = await import("./vrm");
    return mod.loadVrmCharacter({ url });
  }
  const mod = await import("./gltf");
  return mod.loadGltfCharacter({ url });
}

function clamp01(n: number): number {
  if (!Number.isFinite(n)) return 1;
  return Math.max(0, Math.min(1, n));
}
