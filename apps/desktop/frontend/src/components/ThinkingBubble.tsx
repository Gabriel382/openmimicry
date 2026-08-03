import { useEffect, useState } from "react";

import { useRuntimeState } from "../hooks/useRuntimeState";
import { useWS } from "../hooks/useWS";

/** White, non-error progress balloon shown only until a reply starts. */
export function ThinkingBubble(): JSX.Element | null {
  const runtime = useRuntimeState();
  const ws = useWS();
  const [replyStarted, setReplyStarted] = useState(false);

  useEffect(() => {
    setReplyStarted(false);
  }, [runtime.turn?.turn_id]);

  useEffect(() => {
    const offBubble = ws.subscribe("bubble.text", (message) => {
      if (!message.reset && (message.text.length > 0 || message.complete)) {
        setReplyStarted(true);
      }
    });
    const offSpeech = ws.subscribe("speech.status", (message) => {
      if (["ready", "started"].includes(message.status)) setReplyStarted(true);
    });
    return () => {
      offBubble();
      offSpeech();
    };
  }, [ws]);

  if (!runtime.busy || replyStarted) return null;
  return (
    <div className="thinking-bubble" role="status" aria-live="polite">
      <span>THINKING</span>
      <span className="thinking-bubble__dots" aria-hidden="true">
        …
      </span>
    </div>
  );
}
