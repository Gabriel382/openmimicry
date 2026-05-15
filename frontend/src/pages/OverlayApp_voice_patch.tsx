
/*
Merge this into your OverlayApp:
- import VoiceControls from "../voice/VoiceControls";
- import { useVoiceControls } from "../voice/useVoiceControls";
- add the hook calls and JSX
*/

const {
  voice,
  toggleLiveWake,
  togglePushToTalkMode,
  toggleAgentVoice,
  handlePTTStart,
  handlePTTStop,
} = useVoiceControls();

async function onPTTStopAndSubmit() {
  const transcript = await handlePTTStop();
  if (transcript?.trim()) {
    setInput(transcript.trim());
  }
}

// place above the input dock:
<VoiceControls
  voice={voice}
  onToggleLiveWake={toggleLiveWake}
  onTogglePushToTalkMode={togglePushToTalkMode}
  onToggleAgentVoice={toggleAgentVoice}
  onPTTStart={handlePTTStart}
  onPTTStop={onPTTStopAndSubmit}
/>
