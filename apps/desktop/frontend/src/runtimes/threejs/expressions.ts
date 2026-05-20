/**
 * Emotion → VRM expression weights.
 *
 * Mirrors the Python projector in
 * `packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/threejs/projection.py`.
 * The two tables must stay in lockstep — the backend already sends
 * `expressionWeights` over the wire, but the frontend keeps its own
 * copy for the case where a directive arrives without the optional
 * field (older backend, missing key, etc.).
 *
 * `intensity` ∈ [0, 1] scales every weight in the table.
 */

export type Emotion =
  | "neutral"
  | "happy"
  | "sad"
  | "angry"
  | "confused"
  | "focused"
  | "worried";

export type ExpressionWeights = Record<string, number>;

const TABLE: Record<Emotion, ExpressionWeights> = {
  neutral: {},
  happy: { happy: 1.0 },
  sad: { sad: 1.0, neutral: 0.3 },
  angry: { angry: 1.0 },
  confused: { surprised: 0.6, neutral: 0.3 },
  focused: { neutral: 0.3, happy: 0.1 },
  worried: { sad: 0.6, angry: 0.2 },
};

const clamp01 = (n: number): number => Math.max(0, Math.min(1, n));

/**
 * Resolve VRM expression weights for `emotion`. Scales every value by
 * `intensity`. Returns a fresh object on every call.
 */
export function resolveExpression(
  emotion: string | null | undefined,
  intensity: number = 1,
): ExpressionWeights {
  const safeIntensity = clamp01(intensity);
  const key = (emotion ?? "neutral") as Emotion;
  const base = TABLE[key] ?? {};
  const out: ExpressionWeights = {};
  for (const [name, value] of Object.entries(base)) {
    out[name] = clamp01(value * safeIntensity);
  }
  return out;
}

/**
 * Merge several weight tables. Later entries override earlier ones for
 * the same key (no additive blending — the renderer applies weights
 * directly, and adding two `happy=0.6` would push past the unit
 * interval).
 */
export function mergeWeights(...tables: ExpressionWeights[]): ExpressionWeights {
  const out: ExpressionWeights = {};
  for (const table of tables) {
    for (const [name, value] of Object.entries(table)) {
      out[name] = clamp01(value);
    }
  }
  return out;
}
