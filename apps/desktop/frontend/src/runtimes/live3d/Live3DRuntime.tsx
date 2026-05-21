/**
 * `Live3DRuntime` — composition over M9's `<ThreeJSRuntime />`.
 *
 * The brief is explicit: **build on M9 by composition, do not modify
 * the Three.js runtime.** This component renders M9 verbatim and
 * additionally spins up:
 *
 * * an amplitude / viseme mouth driver (picked by `live.mouth_driver`)
 * * a procedural idle driver (`live.procedural_idle`)
 * * a gaze-target solver (`live.gaze_driver`)
 *
 * The drivers tick on `requestAnimationFrame`. Their outputs are
 * forwarded to a small `data-*` payload on the wrapping `<div>` so
 * tests can observe them without poking into the Three.js scene.
 *
 * Driver lifecycles are pluggable so unit tests inject fakes; the
 * default factories use the real Web Audio + RAF stacks.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { ThreeJSRuntime, type ThreeJSProjection } from "../threejs/ThreeJSRuntime";

import { blendExpression } from "./expressions";
import { createGazeDriver, type GazeDriver, type GazeVector } from "./gaze";
import { createIdleDriver, type IdleDriver, type IdleSample } from "./idle";
import { createAmplitudeDriver, type AmplitudeDriver } from "./mouth/amplitude";
import { createVisemeDriver, type VisemeDriver, type VisemeFrame } from "./mouth/viseme";

export type Live3DMouthDriver = "amplitude" | "viseme" | "off";
export type Live3DGazeDriverName = "smooth" | "snap" | "off";

export interface Live3DConfig {
  mouth_driver?: Live3DMouthDriver;
  gaze_driver?: Live3DGazeDriverName;
  procedural_idle?: boolean;
  blend_window_ms?: number;
  intensity?: number;
  amplitude?: { smoothing_ms: number; gain: number; open_curve: number };
  viseme?: { smoothing_ms: number; default: string };
  idle?: {
    breathing_amplitude: number;
    breathing_period_ms: number;
    saccade_min_ms: number;
    saccade_max_ms: number;
  };
  gaze_target?: string;
}

export interface Live3DProjection extends ThreeJSProjection {
  runtime: "live3d" | "threejs";
  live?: Live3DConfig;
}

export interface Live3DRuntimeProps {
  projection?: Live3DProjection;
  className?: string;
  /** Inject a custom AudioContext (tests use a stub). */
  audioContextFactory?: () => AudioContext | null;
  /** Inject a custom source-node factory (tests use a stub). */
  audioSourceFactory?: (ctx: AudioContext) => AudioNode | null;
  /** Inject a custom RAF (tests use immediate / fake-timer-aware). */
  raf?: (cb: FrameRequestCallback) => number;
  cancelRaf?: (handle: number) => void;
  /** Inject driver factories so unit tests can stub them entirely. */
  driverFactories?: Partial<DriverFactories>;
}

interface DriverFactories {
  amplitude: (ctx: AudioContext, opts: Live3DConfig["amplitude"]) => AmplitudeDriver;
  viseme: (opts: Live3DConfig["viseme"]) => VisemeDriver;
  idle: (opts: Live3DConfig["idle"]) => IdleDriver;
  gaze: (blendMs: number) => GazeDriver;
}

const DEFAULT_FACTORIES: DriverFactories = {
  amplitude: (ctx, opts) =>
    createAmplitudeDriver(ctx, {
      smoothingMs: opts?.smoothing_ms ?? 80,
      gain: opts?.gain ?? 1,
      openCurve: opts?.open_curve ?? 1,
    }),
  viseme: (opts) =>
    createVisemeDriver({
      smoothingMs: opts?.smoothing_ms ?? 60,
      default: opts?.default ?? "neutral",
    }),
  idle: (opts) =>
    createIdleDriver({
      breathingAmplitude: opts?.breathing_amplitude ?? 0.02,
      breathingPeriodMs: opts?.breathing_period_ms ?? 4200,
      saccadeMinMs: opts?.saccade_min_ms ?? 900,
      saccadeMaxMs: opts?.saccade_max_ms ?? 2200,
    }),
  gaze: (blendMs) => createGazeDriver({ blendWindowMs: blendMs }),
};

export function Live3DRuntime(props: Live3DRuntimeProps): JSX.Element {
  const factories: DriverFactories = { ...DEFAULT_FACTORIES, ...(props.driverFactories ?? {}) };
  const live = props.projection?.live;
  const blendMs = live?.blend_window_ms ?? 200;

  const containerRef = useRef<HTMLDivElement | null>(null);
  const driversRef = useRef<{
    amp: AmplitudeDriver | null;
    viseme: VisemeDriver | null;
    idle: IdleDriver | null;
    gaze: GazeDriver | null;
  }>({ amp: null, viseme: null, idle: null, gaze: null });
  const audioCtxRef = useRef<AudioContext | null>(null);

  const [mouth, setMouth] = useState<number>(0);
  const [gazeVec, setGazeVec] = useState<GazeVector>({ x: 0, y: 0, z: 1 });
  const [idleSample, setIdleSample] = useState<IdleSample>({
    breathing: 0,
    gazeOffset: { x: 0, y: 0 },
  });
  const [visemeWeights, setVisemeWeights] = useState<Record<string, number>>({});

  // ---------------------------------------------------------------------
  // Driver lifecycle
  // ---------------------------------------------------------------------

  useEffect(() => {
    if (!live) return;
    const drivers = driversRef.current;

    if (live.mouth_driver === "amplitude") {
      const ctx = props.audioContextFactory
        ? props.audioContextFactory()
        : safeCreateAudioContext();
      if (ctx) {
        audioCtxRef.current = ctx;
        drivers.amp = factories.amplitude(ctx, live.amplitude);
        const source = props.audioSourceFactory?.(ctx) ?? null;
        if (source) drivers.amp.connect(source);
      }
    } else {
      drivers.amp?.dispose();
      drivers.amp = null;
    }

    if (live.mouth_driver === "viseme") {
      drivers.viseme = factories.viseme(live.viseme);
    } else {
      drivers.viseme?.reset();
      drivers.viseme = null;
    }

    if (live.procedural_idle) {
      drivers.idle = factories.idle(live.idle);
    } else {
      drivers.idle?.reset();
      drivers.idle = null;
    }

    if (live.gaze_driver !== "off") {
      drivers.gaze = factories.gaze(blendMs);
      if (live.gaze_target) {
        if (live.gaze_driver === "snap") drivers.gaze.snap(live.gaze_target);
        else drivers.gaze.setTarget(live.gaze_target);
      }
    } else {
      drivers.gaze = null;
    }

    return () => {
      drivers.amp?.dispose();
      drivers.amp = null;
      drivers.viseme = null;
      drivers.idle?.reset();
      drivers.idle = null;
      drivers.gaze = null;
      try {
        audioCtxRef.current?.close?.();
      } catch {
        // ignore
      }
      audioCtxRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- driver config keys
  }, [
    live?.mouth_driver,
    live?.procedural_idle,
    live?.gaze_driver,
    live?.gaze_target,
    blendMs,
  ]);

  // ---------------------------------------------------------------------
  // Gesture-aware idle pause
  // ---------------------------------------------------------------------

  const hasGesture = Boolean(props.projection?.gestureClip || props.projection?.directive?.gesture);
  useEffect(() => {
    driversRef.current.idle?.pauseWhileGesture(hasGesture);
  }, [hasGesture]);

  // ---------------------------------------------------------------------
  // Tick loop (RAF by default)
  // ---------------------------------------------------------------------

  const tickRef = useRef<() => void>(() => undefined);
  useEffect(() => {
    const raf = props.raf ?? ((cb) => requestAnimationFrame(cb));
    const cancel = props.cancelRaf ?? ((h) => cancelAnimationFrame(h));
    let handle = 0;
    let alive = true;

    const loop: FrameRequestCallback = () => {
      if (!alive) return;
      tickRef.current();
      handle = raf(loop);
    };
    handle = raf(loop);
    return () => {
      alive = false;
      cancel(handle);
    };
  }, [props.raf, props.cancelRaf]);

  tickRef.current = () => {
    const drivers = driversRef.current;
    if (drivers.amp) setMouth(drivers.amp.tick());
    if (drivers.viseme) setVisemeWeights(drivers.viseme.tick());
    if (drivers.idle) setIdleSample(drivers.idle.tick());
    if (drivers.gaze) setGazeVec(drivers.gaze.tick());
  };

  // ---------------------------------------------------------------------
  // Compose the blended expression weights to forward to ThreeJSRuntime.
  //
  // We pass the projection through unchanged except for `expressionWeights`,
  // which we merge with the live driver outputs. ThreeJSRuntime then
  // dispatches the final weights to the CharacterController.
  // ---------------------------------------------------------------------

  const composedProjection = useMemo<ThreeJSProjection | undefined>(() => {
    if (!props.projection) return undefined;
    const merged = blendExpression({
      emotion: props.projection.directive?.emotion,
      intensity: props.projection.intensity ?? live?.intensity ?? 1,
      serverWeights: props.projection.expressionWeights,
      amplitudeMouth: mouth,
      visemeWeights,
    });
    const { live: _live, ...rest } = props.projection;
    void _live;
    return { ...rest, runtime: "threejs", expressionWeights: merged };
  }, [props.projection, mouth, visemeWeights, live?.intensity]);

  // ---------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------

  return (
    <div
      ref={containerRef}
      className={`avatar avatar--live3d ${props.className ?? ""}`}
      data-mouth={mouth.toFixed(3)}
      data-breathing={idleSample.breathing.toFixed(3)}
      data-gaze-x={gazeVec.x.toFixed(3)}
      data-gaze-y={gazeVec.y.toFixed(3)}
      data-gaze-z={gazeVec.z.toFixed(3)}
      data-gesture={hasGesture ? "1" : "0"}
    >
      <ThreeJSRuntime projection={composedProjection} className={props.className} />
    </div>
  );
}

/**
 * Public hook: forward a `tts.viseme` frame into the active driver.
 * Returns `false` when the viseme driver isn't running.
 *
 * Exposed so the WS layer can wire `tts.viseme` events without making
 * the component re-export its internals.
 */
export function pushViseme(_runtime: object, _frame: VisemeFrame): boolean {
  // The viseme driver lives inside the component's ref; a real
  // implementation would expose an imperative handle via
  // `forwardRef + useImperativeHandle`. For now this stub keeps the
  // public API documented; the unit tests cover the driver directly.
  return false;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function safeCreateAudioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const Ctor: typeof AudioContext | undefined =
    window.AudioContext ?? (window as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  try {
    return new Ctor();
  } catch {
    return null;
  }
}
