import { useEffect, useMemo, useRef, useState } from "react";

import type { RuntimeStateMessage, TurnStateMessage } from "../ws/protocol";
import { useWS } from "./useWS";

const ACTIVE_TURN_STATES = new Set(["accepted", "thinking", "presenting"]);

export interface RuntimeAvailability {
  runtime: RuntimeStateMessage | null;
  turn: TurnStateMessage | null;
  busy: boolean;
  canSubmit: boolean;
  statusLabel: string;
  lastRejection: TurnStateMessage | null;
}

/** Merge connection, process lifecycle, and authoritative turn state. */
export function useRuntimeState(): RuntimeAvailability {
  const ws = useWS();
  const [runtime, setRuntime] = useState<RuntimeStateMessage | null>(null);
  const [turn, setTurn] = useState<TurnStateMessage | null>(null);
  const [lastRejection, setLastRejection] = useState<TurnStateMessage | null>(null);
  const instanceId = useRef<string | null>(null);

  useEffect(() => {
    const offRuntime = ws.subscribe("runtime.state", (message) => {
      if (instanceId.current !== null && instanceId.current !== message.instance_id) {
        setTurn(null);
        setLastRejection(null);
      }
      instanceId.current = message.instance_id;
      setRuntime(message);
    });
    const offTurn = ws.subscribe("turn.state", (message) => {
      if (message.state === "rejected") {
        setLastRejection(message);
        return;
      }
      setTurn((current) => {
        if (ACTIVE_TURN_STATES.has(message.state)) return message;
        if (current === null || current.turn_id === message.turn_id) return message;
        return current;
      });
    });
    return () => {
      offRuntime();
      offTurn();
    };
  }, [ws]);

  return useMemo(() => {
    const busy = turn !== null && ACTIVE_TURN_STATES.has(turn.state);
    // Compatibility fallback: an older backend does not emit runtime.state,
    // but an open socket still remains usable.
    const processReady = runtime === null ? ws.status === "open" : runtime.state === "ready";
    const canSubmit = ws.status === "open" && processReady && !busy;
    const statusLabel =
      ws.status !== "open"
        ? "Backend unavailable"
        : busy
          ? "OpenMimicry is thinking…"
          : runtime?.state === "refreshing"
            ? "Refreshing backend…"
            : runtime !== null && runtime.state !== "ready"
              ? `Backend ${runtime.state}`
              : "Ready";
    return { runtime, turn, busy, canSubmit, statusLabel, lastRejection };
  }, [runtime, turn, ws.status, lastRejection]);
}
