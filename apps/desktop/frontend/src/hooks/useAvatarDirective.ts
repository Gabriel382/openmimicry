/**
 * `useAvatarDirective` — subscribe to `avatar.directive` messages.
 *
 * Returns the most recent `AvatarDirectiveMessage`. Per `contracts.md`
 * §9 the same wire shape carries the full `AvatarDirective` plus
 * runtime-specific extras (frames/fps/loop for Sprite2D, …). Callers
 * pick out what they need.
 */

import { useEffect, useState } from "react";

import { useWS } from "../ws/WSProvider";
import type { AvatarDirectiveMessage } from "../ws/protocol";

export function useAvatarDirective(): AvatarDirectiveMessage | null {
  const ws = useWS();
  const [directive, setDirective] = useState<AvatarDirectiveMessage | null>(
    null,
  );

  useEffect(() => {
    return ws.subscribe("avatar.directive", (msg) => {
      setDirective(msg);
    });
  }, [ws]);

  return directive;
}
