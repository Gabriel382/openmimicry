/**
 * `/overlay` — transparent host. Renders the avatar runtime + speech bubble.
 *
 * No controls live on this route; the docked toolbar and browser dashboard
 * own interaction.
 * The overlay is intentionally minimal so it can be made click-through by
 * the Tauri shell (M8) without interfering with the keyboard focus of
 * other windows.
 */

import type { CSSProperties } from "react";

import { AvatarHost } from "../components/AvatarHost";
import { AvatarStatusBubble } from "../components/AvatarStatusBubble";
import { SpeechBubble } from "../components/SpeechBubble";
import { useAppearance } from "../hooks/useAppearance";

type CustomStyle = CSSProperties & Record<`--om-${string}`, string>;

export function OverlayRoute(): JSX.Element {
  const appearance = useAppearance();
  const style: CustomStyle = {
    "--om-font-family": appearance.theme.font_family,
    "--om-bubble-bg": appearance.theme.bubble_bg,
    "--om-bubble-text": appearance.theme.bubble_text,
    "--om-bubble-max-width": `${appearance.layout.bubble_max_width}px`,
    "--om-avatar-width": `${appearance.layout.avatar_width}px`,
    "--om-avatar-scale": String(appearance.layout.avatar_scale),
  };
  return (
    <div className="overlay-route" data-route="overlay" style={style}>
      <AvatarStatusBubble />
      <AvatarHost />
      <SpeechBubble timing={appearance.behaviour.bubble} />
    </div>
  );
}
