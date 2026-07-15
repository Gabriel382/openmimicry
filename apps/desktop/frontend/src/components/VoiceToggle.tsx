import { useVoiceMode } from "../hooks/useVoiceMode";

export interface VoiceToggleProps {
  className?: string;
}

export function VoiceToggle(props: VoiceToggleProps): JSX.Element {
  const voice = useVoiceMode();
  return (
    <div className={`voice-toggle-wrap ${props.className ?? ""}`}>
      <div className="voice-toggle" role="group" aria-label="Voice modes">
        <button
          type="button"
          aria-pressed={voice.wakeListening}
          onClick={voice.toggleWakeListening}
        >
          Wake listen: {voice.wakeListening ? "on" : "off"}
        </button>
        <button type="button" aria-pressed={voice.agentVoice} onClick={voice.toggleAgentVoice}>
          Agent voice: {voice.agentVoice ? "on" : "off"}
        </button>
      </div>
      <small className="voice-toggle__status">
        Input: {voice.sttAdapter}{voice.realInput ? " (microphone)" : " (mock)"} · Output:{" "}
        {voice.ttsAdapter}{voice.realOutput ? " (audio)" : " (mock)"}
      </small>
      <small className="voice-toggle__hint">
        Hold Ctrl+Space for push-to-talk, or enable Wake listen and begin with {" "}
        {voice.wakeNames[0] ?? "Mimi"}.
      </small>
      {voice.error && <small className="voice-toggle__error" role="alert">{voice.error}</small>}
    </div>
  );
}
