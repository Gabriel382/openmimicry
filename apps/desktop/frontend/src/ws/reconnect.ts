/**
 * Jittered exponential-backoff reconnector for the WS connection.
 *
 * The default strategy:
 *
 * - First retry: `initialMs` (default 250 ms).
 * - Each subsequent retry doubles, capped at `maxMs` (default 10 s).
 * - Adds ±`jitterRatio` × current-delay random jitter (default ±20%).
 * - Stops retrying after `maxAttempts` (default Infinity).
 *
 * Sleep is pluggable so tests can advance fake timers deterministically.
 */

export interface ReconnectConfig {
  initialMs?: number;
  maxMs?: number;
  jitterRatio?: number;
  maxAttempts?: number;
  /** Pluggable sleep (defaults to `setTimeout`). Used by tests. */
  sleep?: (ms: number) => Promise<void>;
  /** Pluggable RNG (defaults to `Math.random`). */
  random?: () => number;
}

export interface ReconnectController {
  /** Next delay in ms (for diagnostics / tests). */
  nextDelay(): number;
  /** Wait one backoff tick. Resolves when it's time to reconnect. */
  wait(): Promise<void>;
  /** Reset attempt counter after a successful open. */
  reset(): void;
  /** Whether more attempts are allowed. */
  hasAttemptsLeft(): boolean;
  /** Current attempt count (0 before the first wait). */
  attempts: number;
}

const DEFAULT_INITIAL_MS = 250;
const DEFAULT_MAX_MS = 10_000;
const DEFAULT_JITTER_RATIO = 0.2;

export function createReconnectController(
  cfg: ReconnectConfig = {},
): ReconnectController {
  const initial = cfg.initialMs ?? DEFAULT_INITIAL_MS;
  const max = cfg.maxMs ?? DEFAULT_MAX_MS;
  const jitter = cfg.jitterRatio ?? DEFAULT_JITTER_RATIO;
  const maxAttempts = cfg.maxAttempts ?? Number.POSITIVE_INFINITY;
  const sleep =
    cfg.sleep ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)));
  const random = cfg.random ?? Math.random;

  let attempts = 0;

  function rawDelay(): number {
    // attempts==0 means "haven't waited yet"; pick `initial`.
    const exp = Math.min(max, initial * Math.pow(2, Math.max(0, attempts)));
    return exp;
  }

  function jittered(base: number): number {
    if (jitter <= 0) return base;
    const spread = base * jitter;
    // Symmetric jitter in [-spread, +spread).
    const offset = (random() - 0.5) * 2 * spread;
    return Math.max(0, base + offset);
  }

  const ctrl: ReconnectController = {
    attempts: 0,
    nextDelay(): number {
      return jittered(rawDelay());
    },
    async wait(): Promise<void> {
      if (!ctrl.hasAttemptsLeft()) return;
      const delay = ctrl.nextDelay();
      attempts += 1;
      ctrl.attempts = attempts;
      await sleep(delay);
    },
    reset(): void {
      attempts = 0;
      ctrl.attempts = 0;
    },
    hasAttemptsLeft(): boolean {
      return attempts < maxAttempts;
    },
  };

  return ctrl;
}
