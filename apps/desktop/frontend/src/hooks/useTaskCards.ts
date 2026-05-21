/**
 * `useTaskCards` — maintain a `Map<handle.id, TaskUpdate>` driven by
 * inbound `task.card` messages. Cancellation is exposed via `cancel(id)`
 * which sends the additive `task.cancel` message defined in
 * `protocol.ts`.
 */

import { useCallback, useEffect, useState } from "react";

import { useWS } from "../ws/WSProvider";
import type { TaskUpdate } from "../ws/protocol";

export interface UseTaskCardsResult {
  /** Ordered by first-seen insertion (`Map` preserves insertion order). */
  cards: TaskUpdate[];
  /** Send `task.cancel` for a given handle id. */
  cancel(id: string): void;
}

export function useTaskCards(): UseTaskCardsResult {
  const ws = useWS();
  const [cardMap, setCardMap] = useState<Map<string, TaskUpdate>>(new Map());

  useEffect(() => {
    return ws.subscribe("task.card", (msg) => {
      setCardMap((prev) => {
        const next = new Map(prev);
        next.set(msg.update.handle.id, msg.update);
        return next;
      });
    });
  }, [ws]);

  const cancel = useCallback(
    (id: string): void => {
      const card = cardMap.get(id);
      if (!card) return;
      ws.send({ type: "task.cancel", handle: card.handle });
    },
    [ws, cardMap],
  );

  return { cards: Array.from(cardMap.values()), cancel };
}
