/**
 * Live3D expression blending.
 *
 * Wraps M9's `resolveExpression` so we can layer:
 *
 * * The base emotion table, scaled by `directive.intensity`.
 * * The optional `expressionWeights` block the backend already sends.
 * * A mouth-driver contribution (amplitude pushes `aa` / `oh`; viseme
 *   driver supplies its own table).
 *
 * The output is a single weights map ready to hand to
 * `CharacterController.setExpression`.
 */

import {
  mergeWeights as mergeWeightsBase,
  resolveExpression as resolveBase,
  type ExpressionWeights,
} from "../threejs/expressions";

export type { ExpressionWeights };

export interface BlendInputs {
  emotion?: string | null;
  intensity?: number;
  /** Whatever the backend already projected for `expressionWeights`. */
  serverWeights?: ExpressionWeights;
  /** Amplitude-mouth contribution in [0, 1]. */
  amplitudeMouth?: number;
  /** Viseme-driver contribution (already smoothed, multi-key). */
  visemeWeights?: ExpressionWeights;
}

/**
 * Compose every contribution into a single weight table. Later entries
 * override earlier ones for the same key, matching the M9 merge rule.
 */
export function blendExpression(inputs: BlendInputs): ExpressionWeights {
  const base = resolveBase(inputs.emotion ?? "neutral", inputs.intensity ?? 1);
  const server = inputs.serverWeights ?? {};
  const amp = amplitudeMouth(inputs.amplitudeMouth ?? 0);
  const viseme = inputs.visemeWeights ?? {};
  return mergeWeightsBase(base, server, amp, viseme);
}

/**
 * Map an amplitude scalar to a two-key VRM jaw-open table. Picks `aa`
 * by default (the most-open neutral viseme) and pushes the lower-lid
 * "lower" hint half as hard so the mouth doesn't look like a fish.
 */
export function amplitudeMouth(amp: number): ExpressionWeights {
  const clamped = amp < 0 ? 0 : amp > 1 ? 1 : amp;
  return {
    aa: clamped,
    oh: clamped * 0.4,
  };
}

export { mergeWeightsBase as mergeWeights };
