/**
 * `<SpeechBubble />` — renders the running bubble text.
 *
 * The hook handles partial accumulation + listening-state reset; this
 * component just paints the result with a small caret indicator while
 * streaming.
 */

import { useEffect, useRef } from "react";

import { useBubbleText } from "../hooks/useBubbleText";

export interface SpeechBubbleProps {
  className?: string;
  timing?: {
    base_ms: number;
    ms_per_character: number;
    min_ms?: number;
    max_ms: number;
  };
}

export function SpeechBubble(props: SpeechBubbleProps): JSX.Element | null {
  const { text, complete } = useBubbleText(props.timing);
  const bubbleRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const bubble = bubbleRef.current;
    if (bubble) bubble.scrollTop = bubble.scrollHeight;
  }, [text]);
  if (!text) return null;
  return (
    <div
      ref={bubbleRef}
      className={`speech-bubble ${props.className ?? ""}`}
      role="status"
      aria-live="polite"
      tabIndex={0}
      title="Enable reply scrolling from the toolbar to use the mouse wheel"
    >
      <span className="speech-bubble__text">{text}</span>
      {!complete && <span className="speech-bubble__caret">▍</span>}
    </div>
  );
}
