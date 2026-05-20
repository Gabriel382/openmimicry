/**
 * `<VoiceToggle />` — live-wake on/off + agent-voice on/off.
 *
 * Tracks the local UI state of both modes optimistically. Server-side
 * authority arrives via `system.notice` `config_updated` messages; we
 * trust the server's diff and snap our local state to it.
 */

import { useEffect, useState } from "react";

import { useWS } from "../hooks/useWS";

export interface VoiceToggleProps {
  initialLiveWake?: boolean;
  initialAgentVoice?: boolean;
  className?: string;
}

export function VoiceToggle(props: VoiceToggleProps): JSX.Element {
  const ws = useWS();
  const [liveWake, setLiveWake] = useState<boolean>(
    props.initialLiveWake ?? false,
  );
  const [agentVoice, setAgentVoice] = useState<boolean>(
    props.initialAgentVoice ?? true,
  );

  useEffect(() => {
    return ws.subscribe("system.notice", (msg) => {
      if (msg.message !== "config_updated") return;
      const diff = (msg.diff ?? {}) as Record<string, unknown>;
      if (typeof diff["live_wake"] === "boolean") {
        setLiveWake(diff["live_wake"]);
      }
      if (typeof diff["agent_voice"] === "boolean") {
        setAgentVoice(diff["agent_voice"]);
      }
    });
  }, [ws]);

  const toggle = (key: "live_wake" | "agent_voice", current: boolean): void => {
    const next = !current;
    ws.send({ type: "mode.toggle", key, value: next });
    if (key === "live_wake") setLiveWake(next);
    else setAgentVoice(next);
  };

  return (
    <div className={`voice-toggle ${props.className ?? ""}`} role="group">
      <button
        type="button"
        aria-pressed={liveWake}
        onClick={() => toggle("live_wake", liveWake)}
      >
        Live wake: {liveWake ? "on" : "off"}
      </button>
      <button
        type="button"
        aria-pressed={agentVoice}
        onClick={() => toggle("agent_voice", agentVoice)}
      >
        Agent voice: {agentVoice ? "on" : "off"}
      </button>
    </div>
  );
}
