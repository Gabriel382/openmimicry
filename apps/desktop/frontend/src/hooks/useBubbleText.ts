/**
 * `useBubbleText` — accumulate `bubble.text` partials.
 *
 * Behaviour:
 *
 * - On a partial (`complete: false`), append the delta to the running buffer.
 * - On a complete message (`complete: true`), REPLACE the buffer with the
 *   full final text. The backend's `LLMReplyComplete` projector sends the
 *   whole reply on `complete`, not just the trailing delta.
 * - On an `avatar.directive` whose `state === "listening"`, clear the
 *   buffer so the bubble doesn't carry stale text into the next turn.
 */

import { useEffect, useState } from "react";

import { useWS } from "../ws/WSProvider";

export interface BubbleState {
  text: string;
  complete: boolean;
}

const EMPTY: BubbleState = { text: "", complete: true };

export function useBubbleText(): BubbleState {
  const ws = useWS();
  const [state, setState] = useState<BubbleState>(EMPTY);

  useEffect(() => {
    const offText = ws.subscribe("bubble.text", (msg) => {
      setState((prev) => {
        if (msg.complete) return { text: msg.text, complete: true };
        return {
          text: (prev.complete ? "" : prev.text) + msg.text,
          complete: false,
        };
      });
    });
    const offDirective = ws.subscribe("avatar.directive", (msg) => {
      if (msg.directive?.state === "listening") {
        setState(EMPTY);
      }
    });
    return () => {
      offText();
      offDirective();
    };
  }, [ws]);

  return state;
}
