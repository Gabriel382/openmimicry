/**
 * Gaze-target solver.
 *
 * Maps the `directive.gaze` string ("towards_user" / "away" / "down" /
 * "screen_center" / "neutral") to a normalised 3D target the renderer
 * positions a HEAD_FOLLOW dummy at. Interpolates over `blendWindowMs`
 * so the transition is smooth; a new target cancels the in-flight
 * blend.
 */

export type GazeName =
  | "towards_user"
  | "away"
  | "down"
  | "up"
  | "left"
  | "right"
  | "screen_center"
  | "neutral";

export interface GazeVector {
  x: number;
  y: number;
  z: number;
}

export interface GazeDriverOptions {
  blendWindowMs: number;
  /** Optional pack-specific override for a name → vector mapping. */
  map?: Record<string, GazeVector>;
  now?: () => number;
}

export interface GazeDriver {
  setTarget(name: string): void;
  /** Sample the current interpolated target. */
  tick(): GazeVector;
  /** Snap immediately (no blend). */
  snap(name: string): void;
  current(): GazeVector;
  reset(): void;
}

const DEFAULT_MAP: Record<string, GazeVector> = {
  towards_user: { x: 0, y: 0, z: 1 },
  away: { x: 0, y: 0.1, z: -1 },
  down: { x: 0, y: -1, z: 0.5 },
  up: { x: 0, y: 1, z: 0.5 },
  left: { x: -1, y: 0, z: 0.5 },
  right: { x: 1, y: 0, z: 0.5 },
  screen_center: { x: 0, y: 0, z: 1 },
  neutral: { x: 0, y: 0, z: 1 },
};

const clamp01 = (v: number): number => (v < 0 ? 0 : v > 1 ? 1 : v);

export function createGazeDriver(opts: GazeDriverOptions): GazeDriver {
  const map = { ...DEFAULT_MAP, ...(opts.map ?? {}) };
  const now = opts.now ?? (() => performance.now());

  let current: GazeVector = { ...map.towards_user! };
  let target: GazeVector = { ...current };
  let blendStart = now();
  let blendFrom: GazeVector = { ...current };

  const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;
  const resolve = (name: string): GazeVector =>
    map[name] ? { ...map[name]! } : { ...current };

  return {
    setTarget(name: string): void {
      target = resolve(name);
      blendStart = now();
      blendFrom = { ...current };
    },
    tick(): GazeVector {
      const t = now();
      const elapsed = t - blendStart;
      const ratio = clamp01(elapsed / Math.max(1, opts.blendWindowMs));
      current = {
        x: lerp(blendFrom.x, target.x, ratio),
        y: lerp(blendFrom.y, target.y, ratio),
        z: lerp(blendFrom.z, target.z, ratio),
      };
      return { ...current };
    },
    snap(name: string): void {
      current = resolve(name);
      target = { ...current };
      blendFrom = { ...current };
      blendStart = now();
    },
    current(): GazeVector {
      return { ...current };
    },
    reset(): void {
      current = { ...map.towards_user! };
      target = { ...current };
      blendFrom = { ...current };
      blendStart = now();
    },
  };
}
