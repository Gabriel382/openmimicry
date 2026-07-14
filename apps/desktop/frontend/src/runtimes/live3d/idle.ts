/**
 * Procedural idle motion: breathing wave + micro-saccades.
 *
 * The driver is paused while a `gesture` clip is playing (per the M10
 * test surface: "Procedural idle does not run while a `gesture` clip is
 * playing"). Callers pin `pauseWhileGesture(true)` on the way in and
 * `pauseWhileGesture(false)` on the way out.
 *
 * Pure logic — no Three.js dependency. The runtime calls `tick()` once
 * per frame and applies the returned deltas to whatever bones / camera
 * offsets the renderer exposes.
 */

export interface IdleDriverOptions {
  breathingAmplitude: number;
  breathingPeriodMs: number;
  saccadeMinMs: number;
  saccadeMaxMs: number;
  now?: () => number;
  random?: () => number;
}

export interface IdleSample {
  /** Vertical bob amplitude (in pack units). */
  breathing: number;
  /** Eye-target offset in normalized -1..1 space. */
  gazeOffset: { x: number; y: number };
}

export interface IdleDriver {
  tick(): IdleSample;
  /** Toggle pause; `tick()` returns frozen sample while paused. */
  pauseWhileGesture(paused: boolean): void;
  reset(): void;
}

const TAU = Math.PI * 2;
const clamp = (v: number, lo: number, hi: number): number =>
  v < lo ? lo : v > hi ? hi : v;

export function createIdleDriver(opts: IdleDriverOptions): IdleDriver {
  const now = opts.now ?? (() => performance.now());
  const random = opts.random ?? Math.random;
  const t0 = now();

  let paused = false;
  let nextSaccade = scheduleNext(t0);
  let currentGaze = { x: 0, y: 0 };
  let lastSample: IdleSample = { breathing: 0, gazeOffset: { x: 0, y: 0 } };

  function scheduleNext(at: number): number {
    const lo = Math.max(100, opts.saccadeMinMs);
    const hi = Math.max(lo, opts.saccadeMaxMs);
    return at + (lo + random() * (hi - lo));
  }

  return {
    tick(): IdleSample {
      if (paused) return lastSample;
      const t = now();
      const phase = ((t - t0) / Math.max(1, opts.breathingPeriodMs)) * TAU;
      const breathing = Math.sin(phase) * opts.breathingAmplitude;

      if (t >= nextSaccade) {
        // Tiny eye-target offset in normalised space, biased toward
        // small movements (humans usually don't dart their eyes).
        const ax = (random() - 0.5) * 0.4;
        const ay = (random() - 0.5) * 0.2;
        currentGaze = { x: clamp(ax, -1, 1), y: clamp(ay, -1, 1) };
        nextSaccade = scheduleNext(t);
      }
      lastSample = { breathing, gazeOffset: { ...currentGaze } };
      return lastSample;
    },
    pauseWhileGesture(p: boolean): void {
      paused = p;
    },
    reset(): void {
      paused = false;
      currentGaze = { x: 0, y: 0 };
      nextSaccade = scheduleNext(now());
      lastSample = { breathing: 0, gazeOffset: { x: 0, y: 0 } };
    },
  };
}
