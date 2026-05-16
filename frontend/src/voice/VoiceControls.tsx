
import React from "react"
import type { VoiceStatus } from "./types"

type Props = {
  voice: VoiceStatus | null
  onToggleLiveWake: () => void
  onTogglePushToTalkMode: () => void
  onToggleAgentVoice: () => void
  onPTTStart: () => void
  onPTTStop: () => void
}

export default function VoiceControls(props: Props) {
  const { voice } = props
  return (
    <div className="voice-controls">
      <button className={`voice-btn ${voice?.live_wake_enabled ? "active" : ""}`} onClick={props.onToggleLiveWake}>Live Wake</button>
      <button className={`voice-btn ${voice?.push_to_talk_enabled ? "active" : ""}`} onClick={props.onTogglePushToTalkMode}>Hold to Talk</button>
      <button className={`voice-btn ${voice?.agent_voice_enabled ? "active" : ""}`} onClick={props.onToggleAgentVoice}>Agent Voice</button>
      <button className="voice-btn ptt" onMouseDown={props.onPTTStart} onMouseUp={props.onPTTStop} onMouseLeave={props.onPTTStop} onTouchStart={props.onPTTStart} onTouchEnd={props.onPTTStop}>Hold</button>
      <div className="voice-state">{voice ? `${voice.mode} · ${voice.runtime_state}` : "voice unavailable"}</div>
    </div>
  )
}
