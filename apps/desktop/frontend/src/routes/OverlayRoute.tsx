/**
 * `/overlay` — transparent host. Renders the avatar runtime + speech bubble.
 *
 * No text input or settings live on this route; the panel route owns those.
 * The overlay is intentionally minimal so it can be made click-through by
 * the Tauri shell (M8) without interfering with the keyboard focus of
 * other windows.
 */

import { AvatarHost } from "../components/AvatarHost";
import { SpeechBubble } from "../components/SpeechBubble";

export function OverlayRoute(): JSX.Element {
  return (
    <div className="overlay-route" data-route="overlay">
      <AvatarHost />
      <SpeechBubble />
    </div>
  );
}
