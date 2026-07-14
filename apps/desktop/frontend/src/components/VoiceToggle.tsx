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
  const [sttAdapter, setSttAdapter] = useState<string>("unknown");
  const [ttsAdapter, setTtsAdapter] = useState<string>("unknown");
  const [realInput, setRealInput] = useState<boolean>(false);
  const [realOutput, setRealOutput] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    return ws.subscribe("system.notice", (msg) => {
      if (msg.message === "voice_status" && msg.voice) {
        if (typeof msg.voice.live_wake === "boolean") setLiveWake(msg.voice.live_wake);
        if (typeof msg.voice.agent_voice === "boolean") setAgentVoice(msg.voice.agent_voice);
        if (typeof msg.voice.stt_adapter === "string") setSttAdapter(msg.voice.stt_adapter);
        if (typeof msg.voice.tts_adapter === "string") setTtsAdapter(msg.voice.tts_adapter);
        setRealInput(msg.voice.real_input === true);
        setRealOutput(msg.voice.real_output === true);
        return;
      }
      if (msg.level === "error" && msg.where === "voice.mode") {
        setError(msg.message);
        return;
      }
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
    setError(null);
    const next = !current;
    ws.send({ type: "mode.toggle", key, value: next });
    if (key === "live_wake") setLiveWake(next);
    else setAgentVoice(next);
  };

  return (
    <div className={`voice-toggle-wrap ${props.className ?? ""}`}>
      <div className="voice-toggle" role="group">
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
      <small className="voice-toggle__status">
        Input: {sttAdapter}{realInput ? " (microphone)" : " (mock)"} · Output: {ttsAdapter}
        {realOutput ? " (audio)" : " (mock)"}
      </small>
      {(!realInput || !realOutput) && (
        <small className="voice-toggle__hint">
          Mock voice changes state for testing but cannot hear or play audio. Use the
          openrouter-voice profile for local free speech.
        </small>
      )}
      {error && <small className="voice-toggle__error" role="alert">{error}</small>}
    </div>
  );
}
