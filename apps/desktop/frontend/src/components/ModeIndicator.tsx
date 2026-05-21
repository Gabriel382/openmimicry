/**
 * `<ModeIndicator />` — small status chip reflecting current avatar state
 * + WS connection status. Reads `useAvatarDirective` + `useWS().status`.
 */

import { useAvatarDirective } from "../hooks/useAvatarDirective";
import { useWS } from "../hooks/useWS";

export function ModeIndicator(props: { className?: string }): JSX.Element {
  const directive = useAvatarDirective();
  const { status } = useWS();
  const state = directive?.directive?.state ?? "idle";
  return (
    <div
      className={`mode-indicator ${props.className ?? ""}`}
      role="status"
      aria-label="mode indicator"
      data-state={state}
      data-ws-status={status}
    >
      <span className="mode-indicator__dot" data-status={status} />
      <span className="mode-indicator__state">{state}</span>
      <span className="mode-indicator__ws">[{status}]</span>
    </div>
  );
}
