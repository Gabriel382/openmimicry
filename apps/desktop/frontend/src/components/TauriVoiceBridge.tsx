import { useEffect } from "react";

import { useWS } from "../hooks/useWS";

export function TauriVoiceBridge(): null {
  const ws = useWS();

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!("__TAURI_INTERNALS__" in window || "__TAURI_IPC__" in window)) return;

    let disposed = false;
    const cleanups: Array<() => void> = [];
    void import("@tauri-apps/api/event").then(async ({ listen }) => {
      const offDown = await listen("ptt:down", () => ws.send({ type: "ptt.down" }));
      const offUp = await listen("ptt:up", () => ws.send({ type: "ptt.up" }));
      if (disposed) {
        offDown();
        offUp();
      } else {
        cleanups.push(offDown, offUp);
      }
    });

    return () => {
      disposed = true;
      cleanups.forEach((cleanup) => cleanup());
    };
  }, [ws]);

  return null;
}
