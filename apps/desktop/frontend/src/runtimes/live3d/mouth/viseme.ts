/**
 * Viseme-based mouth driver.
 *
 * Consumes `tts.viseme` events (additive amendment to the §9 wire
 * protocol) and resolves them to VRM viseme weights. The mapping is
 * intentionally tiny — packs override via `runtime_cfg.viseme.map`.
 *
 * The driver also smooths transitions between adjacent visemes so the
 * mouth doesn't snap. `currentWeights()` returns the active mix.
 */

export type VisemeName =
  | "neutral"
  | "aa"
  | "ee"
  | "ih"
  | "oh"
  | "ou"
  | "consonant"
  | "smile";

export interface VisemeFrame {
  /** Viseme name as published over WS. */
  viseme: string;
  /** Optional override of the default weight (defaults to 1.0). */
  weight?: number;
}

export interface VisemeDriverOptions {
  /** Smoothing time constant (ms) for blend between consecutive visemes. */
  smoothingMs: number;
  /** Optional pack-supplied map of viseme → VRM expression key. */
  map?: Record<string, string>;
  /** Default viseme to emit when no frame has arrived. */
  default?: string;
  /** Pluggable now-source for tests. */
  now?: () => number;
}

export interface VisemeDriver {
  push(frame: VisemeFrame): void;
  /** Sample and return the current weight table (already smoothed). */
  tick(): Record<string, number>;
  currentWeights(): Record<string, number>;
  reset(): void;
}

const DEFAULT_MAP: Record<string, string> = {
  neutral: "neutral",
  aa: "aa",
  ee: "ee",
  ih: "ih",
  oh: "oh",
  ou: "ou",
  consonant: "neutral",
  smile: "happy",
};

const clamp01 = (v: number): number => (v < 0 ? 0 : v > 1 ? 1 : v);

export function createVisemeDriver(opts: VisemeDriverOptions): VisemeDriver {
  const map = { ...DEFAULT_MAP, ...(opts.map ?? {}) };
  const now = opts.now ?? (() => performance.now());

  let target: { key: string; weight: number } = {
    key: map[opts.default ?? "neutral"] ?? "neutral",
    weight: 1,
  };
  let weights: Record<string, number> = { [target.key]: 1 };
  let lastTick = now();

  return {
    push(frame: VisemeFrame): void {
      const key = map[frame.viseme] ?? map["neutral"]!;
      target = { key, weight: clamp01(frame.weight ?? 1) };
    },
    tick(): Record<string, number> {
      const t = now();
      const dt = Math.max(0, t - lastTick);
      lastTick = t;
      const tau = Math.max(1, opts.smoothingMs);
      const alpha = dt / (tau + dt);

      // Move every existing key toward 0 unless it matches `target.key`.
      const next: Record<string, number> = {};
      for (const [key, value] of Object.entries(weights)) {
        if (key === target.key) continue;
        const v = value + alpha * (0 - value);
        if (v > 0.001) next[key] = v;
      }
      const currentTarget = weights[target.key] ?? 0;
      next[target.key] = clamp01(currentTarget + alpha * (target.weight - currentTarget));
      weights = next;
      return { ...weights };
    },
    currentWeights(): Record<string, number> {
      return { ...weights };
    },
    reset(): void {
      target = { key: map[opts.default ?? "neutral"] ?? "neutral", weight: 1 };
      weights = { [target.key]: 1 };
    },
  };
}
