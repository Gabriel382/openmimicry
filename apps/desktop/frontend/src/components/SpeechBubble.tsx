/**
 * `<SpeechBubble />` — renders the running bubble text.
 *
 * The hook handles partial accumulation + listening-state reset; this
 * component just paints the result with a small caret indicator while
 * streaming.
 */

import { useBubbleText } from "../hooks/useBubbleText";

export interface SpeechBubbleProps {
  className?: string;
}

export function SpeechBubble(props: SpeechBubbleProps): JSX.Element | null {
  const { text, complete } = useBubbleText();
  if (!text) return null;
  return (
    <div
      className={`speech-bubble ${props.className ?? ""}`}
      role="status"
      aria-live="polite"
    >
      <span className="speech-bubble__text">{text}</span>
      {!complete && <span className="speech-bubble__caret">▍</span>}
    </div>
  );
}
