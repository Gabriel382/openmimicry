/**
 * `useBubbleText` — accumulate `bubble.text` partials.
 *
 * Behaviour:
 *
 * - On a partial (`complete: false`), append the delta to the running buffer.
 * - On a complete message (`complete: true`), REPLACE the buffer with the
 *   full final text. The backend's `LLMReplyComplete` projector sends the
 *   whole reply on `complete`, not just the trailing delta.
 * - A completed reply remains visible for a configurable reading-time
 *   formula. The next partial replaces it immediately.
 */

import { useEffect, useState } from "react";

import { useWS } from "../ws/WSProvider";

export interface BubbleState {
  text: string;
  complete: boolean;
}

const EMPTY: BubbleState = { text: "", complete: true };

export interface BubbleTiming {
  base_ms: number;
  ms_per_character: number;
  max_ms: number;
}

const DEFAULT_TIMING: BubbleTiming = {
  base_ms: 2500,
  ms_per_character: 55,
  max_ms: 30000,
};

export function useBubbleText(timing: BubbleTiming = DEFAULT_TIMING): BubbleState {
  const ws = useWS();
  const [state, setState] = useState<BubbleState>(EMPTY);

  useEffect(() => {
    const offText = ws.subscribe("bubble.text", (msg) => {
      setState((prev) => {
        if (msg.reset) return EMPTY;
        if (msg.complete) return { text: msg.text, complete: true };
        return {
          text: (prev.complete ? "" : prev.text) + msg.text,
          complete: false,
        };
      });
    });
    return () => {
      offText();
    };
  }, [ws]);

  useEffect(() => {
    if (!state.text || !state.complete) return;
    const readingMs = Math.min(
      timing.max_ms,
      timing.base_ms + state.text.length * timing.ms_per_character,
    );
    const handle = window.setTimeout(() => setState(EMPTY), readingMs);
    return () => window.clearTimeout(handle);
  }, [state.complete, state.text, timing.base_ms, timing.max_ms, timing.ms_per_character]);

  return state;
}
