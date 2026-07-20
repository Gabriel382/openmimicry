import { useRuntimeState } from "../hooks/useRuntimeState";
import { useVoiceMode } from "../hooks/useVoiceMode";

/** Operational state belongs beside the avatar; toolbar red is error-only. */
export function AvatarStatusBubble(): JSX.Element | null {
  const runtime = useRuntimeState();
  const voice = useVoiceMode();

  let state: "listening" | "transcribing" | "thinking" | "backend" | null = null;
  let label = "";
  if (voice.pttStage === "listening") {
    state = "listening";
    label = "Listening…";
  } else if (voice.pttStage === "transcribing") {
    state = "transcribing";
    label = "Transcribing…";
  } else if (runtime.busy) {
    state = "thinking";
    label = "Thinking…";
  } else if (!runtime.canSubmit) {
    state = "backend";
    label = runtime.statusLabel;
  }

  if (state === null) return null;
  return (
    <div className="avatar-status-bubble" data-state={state} role="status" aria-live="polite">
      {label}
    </div>
  );
}
