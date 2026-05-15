
export async function getVoiceStatus() {
  const r = await fetch("http://localhost:8000/voice/status")
  return await r.json()
}
export async function setLiveWake(enabled: boolean) {
  const r = await fetch("http://localhost:8000/voice/live-wake", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled })
  })
  return await r.json()
}
export async function setPushToTalkMode(enabled: boolean) {
  const r = await fetch("http://localhost:8000/voice/push-to-talk-mode", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled })
  })
  return await r.json()
}
export async function setAgentVoice(enabled: boolean) {
  const r = await fetch("http://localhost:8000/voice/agent-voice", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled })
  })
  return await r.json()
}
export async function startPTT() {
  const r = await fetch("http://localhost:8000/voice/ptt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "start" })
  })
  return await r.json()
}
export async function stopPTT() {
  const r = await fetch("http://localhost:8000/voice/ptt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "stop" })
  })
  return await r.json()
}
export async function interruptVoice() {
  const r = await fetch("http://localhost:8000/voice/interrupt", { method: "POST" })
  return await r.json()
}
