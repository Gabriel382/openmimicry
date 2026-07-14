/**
 * State + gesture → animation-clip selection.
 *
 * The backend's Three.js projection already includes a `clip` (best
 * guess) plus a `fallbackClips` chain. The frontend tries them in order
 * against the loaded glTF/VRM's actual clip manifest and picks the
 * first hit. If nothing matches, it defaults to `"idle"`.
 */

export interface PickClipOptions {
  state: string;
  emotion?: string | null;
  speaking?: boolean;
  gesture?: string | null;
  available: string[];
}

/**
 * Resolve a single clip name from a directive shape + a manifest of
 * available clip names. Pure function — no DOM, no Three.js.
 *
 * Order:
 *   1. `<emotion>_<state>_speaking` (when `speaking` is true)
 *   2. `<state>_speaking` (when `speaking` is true)
 *   3. `<emotion>_<state>`
 *   4. `<state>`
 *   5. `idle`
 *
 * `gesture` is layered separately by `pickGestureClip`. The main clip
 * is the body animation; gesture is a one-shot overlay.
 */
export function pickClip(opts: PickClipOptions): string {
  const { state, emotion, speaking, available } = opts;
  const chain = clipFallbackChain(state, emotion ?? "neutral", Boolean(speaking));
  const set = new Set(available);
  for (const name of chain) {
    if (set.has(name)) return name;
  }
  return set.has("idle") ? "idle" : (chain[chain.length - 1] ?? "idle");
}

export function clipFallbackChain(
  state: string,
  emotion: string,
  speaking: boolean,
): string[] {
  const chain: string[] = [];
  if (speaking) {
    chain.push(`${emotion}_${state}_speaking`);
    chain.push(`${state}_speaking`);
  }
  chain.push(`${emotion}_${state}`);
  chain.push(state);
  if (!chain.includes("idle")) chain.push("idle");
  // de-dup while preserving order
  return Array.from(new Set(chain));
}

/**
 * Resolve a one-shot gesture clip name from the manifest. Returns
 * `null` when no compatible clip exists — the renderer skips the
 * gesture rather than picking a wrong one.
 */
export function pickGestureClip(
  gesture: string | null | undefined,
  available: string[],
): string | null {
  if (!gesture) return null;
  if (available.includes(gesture)) return gesture;
  // Some packs prefix gestures with `gesture_`. Try that too.
  const prefixed = `gesture_${gesture}`;
  if (available.includes(prefixed)) return prefixed;
  return null;
}
