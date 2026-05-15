
import { useEffect, useRef, useState } from "react"
import { getVoiceStatus, interruptVoice, setAgentVoice, setLiveWake, setPushToTalkMode, startPTT, stopPTT } from "./api"
import type { VoiceStatus } from "./types"

export function useVoiceControls() {
  const [voice, setVoice] = useState<VoiceStatus | null>(null)
  const pollRef = useRef<number | null>(null)

  async function refresh() {
    const status = await getVoiceStatus()
    setVoice(status)
    return status
  }

  useEffect(() => {
    refresh()
    pollRef.current = window.setInterval(refresh, 1200)
    return () => {
      if (pollRef.current !== null) window.clearInterval(pollRef.current)
    }
  }, [])

  async function toggleLiveWake() {
    if (!voice) return
    setVoice(await setLiveWake(!voice.live_wake_enabled))
  }
  async function togglePushToTalkMode() {
    if (!voice) return
    setVoice(await setPushToTalkMode(!voice.push_to_talk_enabled))
  }
  async function toggleAgentVoice() {
    if (!voice) return
    setVoice(await setAgentVoice(!voice.agent_voice_enabled))
  }
  async function handlePTTStart() {
    await interruptVoice()
    setVoice(await startPTT())
  }
  async function handlePTTStop() {
    const next = await stopPTT()
    setVoice(next)
    return next?.transcript ?? ""
  }
  async function interrupt() {
    await interruptVoice()
    await refresh()
  }

  return { voice, refresh, toggleLiveWake, togglePushToTalkMode, toggleAgentVoice, handlePTTStart, handlePTTStop, interrupt }
}
