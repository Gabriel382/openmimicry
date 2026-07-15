import { useCallback, useEffect, useState } from "react";

import { useWS } from "./useWS";

export interface VoiceModeState {
  wakeListening: boolean;
  wakeNames: string[];
  agentVoice: boolean;
  pttActive: boolean;
  sttAdapter: string;
  ttsAdapter: string;
  realInput: boolean;
  realOutput: boolean;
  error: string | null;
  toggleWakeListening(): void;
  toggleAgentVoice(): void;
  pttDown(): void;
  pttUp(): void;
}

export function useVoiceMode(): VoiceModeState {
  const { send, subscribe } = useWS();
  const [wakeListening, setWakeListening] = useState(false);
  const [wakeNames, setWakeNames] = useState<string[]>(["Mimi", "Hey Mimi"]);
  const [agentVoice, setAgentVoice] = useState(true);
  const [pttActive, setPttActive] = useState(false);
  const [sttAdapter, setSttAdapter] = useState("unknown");
  const [ttsAdapter, setTtsAdapter] = useState("unknown");
  const [realInput, setRealInput] = useState(false);
  const [realOutput, setRealOutput] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    return subscribe("system.notice", (message) => {
      if (message.message === "voice_status" && message.voice) {
        if (typeof message.voice.live_wake === "boolean") {
          setWakeListening(message.voice.live_wake);
        }
        if (Array.isArray(message.voice.wake_names)) {
          setWakeNames(message.voice.wake_names);
        }
        if (typeof message.voice.agent_voice === "boolean") {
          setAgentVoice(message.voice.agent_voice);
        }
        if (typeof message.voice.ptt_active === "boolean") {
          setPttActive(message.voice.ptt_active);
        }
        if (typeof message.voice.stt_adapter === "string") {
          setSttAdapter(message.voice.stt_adapter);
        }
        if (typeof message.voice.tts_adapter === "string") {
          setTtsAdapter(message.voice.tts_adapter);
        }
        setRealInput(message.voice.real_input === true);
        setRealOutput(message.voice.real_output === true);
        const hint = message.voice.input_install_hint ?? message.voice.output_install_hint;
        if (typeof hint === "string" && hint) setError(hint);
        return;
      }

      if (message.level === "error" && message.where?.startsWith("voice.")) {
        setError(message.message);
        setPttActive(false);
        if (message.where === "voice.mode") setWakeListening(false);
        return;
      }
      if (message.message !== "config_updated") return;
      const diff = message.diff ?? {};
      if (typeof diff.live_wake === "boolean") {
        setWakeListening(diff.live_wake);
      }
      if (Array.isArray(diff.wake_names)) {
        setWakeNames(diff.wake_names.filter((name): name is string => typeof name === "string"));
      }
      if (typeof diff.agent_voice === "boolean") setAgentVoice(diff.agent_voice);
      if (typeof diff.ptt_active === "boolean") setPttActive(diff.ptt_active);
    });
  }, [subscribe]);

  const toggleWakeListening = useCallback((): void => {
    setError(null);
    const next = !wakeListening;
    setWakeListening(next);
    send({ type: "mode.toggle", key: "live_wake", value: next });
  }, [send, wakeListening]);

  const toggleAgentVoice = useCallback((): void => {
    setError(null);
    const next = !agentVoice;
    setAgentVoice(next);
    send({ type: "mode.toggle", key: "agent_voice", value: next });
  }, [agentVoice, send]);

  const pttDown = useCallback((): void => {
    setError(null);
    setPttActive(true);
    send({ type: "ptt.down" });
  }, [send]);

  const pttUp = useCallback((): void => {
    setPttActive(false);
    send({ type: "ptt.up" });
  }, [send]);

  return {
    wakeListening,
    wakeNames,
    agentVoice,
    pttActive,
    sttAdapter,
    ttsAdapter,
    realInput,
    realOutput,
    error,
    toggleWakeListening,
    toggleAgentVoice,
    pttDown,
    pttUp,
  };
}
