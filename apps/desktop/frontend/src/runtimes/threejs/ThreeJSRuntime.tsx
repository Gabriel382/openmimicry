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
import { createScene, type SceneHandles } from "./scene";
import {
  applyModelTransform,
  captureModelBasis,
  type ModelBasis,
  type ModelTransform,
} from "./transform";
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
  animationSpeed?: number;
  animations?: Record<string, string>;
  transform?: ModelTransform;
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
  const sceneRef = useRef<SceneHandles | null>(null);
  const canvasRef = useRef<Node | null>(null);
  const basisRef = useRef<ModelBasis | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  const assetUrl = projection?.asset?.url ?? null;
  const assetKind = projection?.asset?.kind ?? "vrm";
  const animationManifestKey = useMemo(
    () =>
      JSON.stringify(
        Object.entries(projection?.animations ?? {}).sort(([left], [right]) =>
          left.localeCompare(right),
        ),
      ),
    [projection?.animations],
  );
  const transformKey = useMemo(
    () => JSON.stringify(projection?.transform ?? null),
    [projection?.transform],
  );

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
        let ctrl: CharacterController;
        if (loader) {
          ctrl = await loader(assetUrl);
        } else {
          const host = containerRef.current;
          if (!host) throw new Error("Three.js mount is unavailable");
          const width = Math.max(1, host.clientWidth || 360);
          const height = Math.max(1, host.clientHeight || 360);
          const handles = createScene({ width, height, lighting: "studio" });
          if (canvasRef.current?.parentNode === host) {
            host.removeChild(canvasRef.current);
          }
          sceneRef.current?.dispose();
          sceneRef.current = handles;
          const canvas = (handles.renderer as unknown as { domElement?: Node }).domElement;
          if (canvas) {
            host.appendChild(canvas);
            canvasRef.current = canvas;
          }
          ctrl = await defaultLoad(assetUrl, assetKind, handles.scene);
        }
        if (ctrl.loadAnimation) {
          const animations = JSON.parse(animationManifestKey) as [string, string][];
          for (const [name, url] of animations) {
            await ctrl.loadAnimation(url, name);
          }
        }
        if (cancelled) {
          ctrl.dispose();
          return;
        }
        controllerRef.current?.dispose();
        controllerRef.current = ctrl;
        try {
          basisRef.current = captureModelBasis(ctrl.root);
          applyModelTransform(
            ctrl.root,
            basisRef.current,
            projection?.transform,
          );
        } catch {
          // Injected/test controllers and unusual loaders may expose a
          // non-Three root. Rendering and animation remain usable; only
          // dashboard transform controls are unavailable for that asset.
          basisRef.current = null;
        }
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
  }, [
    assetUrl,
    assetKind,
    props.vrmLoader,
    props.gltfLoader,
    animationManifestKey,
  ]);

  // Tear down the controller on unmount.
  useEffect(() => {
    return () => {
      controllerRef.current?.dispose();
      controllerRef.current = null;
      basisRef.current = null;
      sceneRef.current?.dispose();
      sceneRef.current = null;
      canvasRef.current?.parentNode?.removeChild(canvasRef.current);
      canvasRef.current = null;
    };
  }, []);

  useEffect(() => {
    const controller = controllerRef.current;
    const basis = basisRef.current;
    if (!controller || !basis) return;
    applyModelTransform(controller.root, basis, projection?.transform);
  }, [status, transformKey]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    let frame = 0;
    let previous = performance.now();
    const render = (now: number) => {
      const delta = Math.min(0.1, Math.max(0, (now - previous) / 1000));
      previous = now;
      const speed = Math.max(0.1, Math.min(4, projection?.animationSpeed ?? 1));
      controllerRef.current?.update?.(delta * speed);
      scene.renderer.render(scene.scene, scene.camera);
      frame = requestAnimationFrame(render);
    };
    frame = requestAnimationFrame(render);
    return () => cancelAnimationFrame(frame);
  }, [status, projection?.animationSpeed]);

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
  }, [computed, status]);

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
  scene: import("three").Scene,
): Promise<CharacterController> {
  if (kind === "vrm") {
    const mod = await import("./vrm");
    return mod.loadVrmCharacter({ url, scene });
  }
  const mod = await import("./gltf");
  return mod.loadGltfCharacter({ url, scene });
}

function clamp01(n: number): number {
  if (!Number.isFinite(n)) return 1;
  return Math.max(0, Math.min(1, n));
}
