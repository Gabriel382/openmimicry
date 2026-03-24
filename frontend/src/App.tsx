
import React, { useEffect, useMemo, useState } from 'react'
import { getConfig, getHealth, postChat, postTts } from './api'
import { speakWithBrowserVoice } from './tts/browserVoice'

export default function App() {
  const [config, setConfig] = useState<any>(null)
  const [health, setHealth] = useState<any>(null)
  const [messages, setMessages] = useState<any[]>([])
  const [input, setInput] = useState('')
  const [mode, setMode] = useState<'overlay'|'panel'|'split'>('split')
  const [currentAnimation, setCurrentAnimation] = useState('idle')
  const [bubbleText, setBubbleText] = useState('')
  const [frameUrl, setFrameUrl] = useState<string | null>(null)
  const [frameIndex, setFrameIndex] = useState(0)

  useEffect(() => { getConfig().then(setConfig); getHealth().then(setHealth) }, [])

  const character = config?.character
  const theme = config?.theme
  const personality = config?.personality
  const currentFrames = useMemo(() => character?.animations?.[currentAnimation]?.frames ?? [], [character, currentAnimation])

  useEffect(() => {
    if (!currentFrames.length) return
    setFrameUrl(`http://localhost:8000/static/${currentFrames[0]}`)
    setFrameIndex(0)
    const fps = character?.animations?.[currentAnimation]?.fps ?? 6
    const timer = window.setInterval(() => {
      setFrameIndex(prev => {
        const next = (prev + 1) % currentFrames.length
        setFrameUrl(`http://localhost:8000/static/${currentFrames[next]}`)
        return next
      })
    }, Math.max(80, Math.floor(1000 / fps)))
    return () => window.clearInterval(timer)
  }, [currentFrames, currentAnimation, character])

  useEffect(() => {
    if (character?.default_state) setCurrentAnimation(character.default_state)
  }, [character])

  async function onSend() {
    const text = input.trim()
    if (!text) return
    setMessages(prev => [...prev, { role: 'user', text }])
    setInput('')
    setCurrentAnimation(character?.thinking_animation ?? 'thinking')
    setBubbleText('Thinking...')
    const res = await postChat(text)
    setMessages(prev => [...prev, { role: 'assistant', text: res.text, avatar: res.avatar, backend: res.backend }])
    setCurrentAnimation(res.avatar.animation)
    setBubbleText(res.text)
    const ok = speakWithBrowserVoice(res.text)
    if (!ok) await postTts(res.text)
    window.setTimeout(() => {
      setCurrentAnimation(res.avatar.next_state || 'idle')
      setBubbleText('')
    }, 2200)
  }

  if (!config) return <div className="boot">Loading OpenMimicry…</div>

  const colors = theme?.colors ?? {}
  return (
    <div className={`app-shell mode-${mode}`}>
      <div className="mode-switch">
        <button onClick={() => setMode('overlay')}>Overlay</button>
        <button onClick={() => setMode('panel')}>Panel</button>
        <button onClick={() => setMode('split')}>Split</button>
      </div>

      {(mode === 'overlay' || mode === 'split') && (
        <div className="overlay-root">
          {bubbleText ? <div className="bubble" style={{ background: colors.bubble_bg, color: colors.bubble_text }}>{bubbleText}</div> : null}
          <div className="avatar-stage">
            {frameUrl ? <img src={frameUrl} className="avatar-image" alt={currentAnimation} /> : null}
          </div>
          <div className="avatar-badge">{currentAnimation}</div>
        </div>
      )}

      {(mode === 'panel' || mode === 'split') && (
        <div className="panel-root" style={{ background: colors.panel_bg, color: colors.text_primary, borderColor: colors.panel_border }}>
          <div className="panel-header">
            <div>
              <div className="panel-title">OpenMimicry</div>
              <div className="panel-subtitle">{personality?.name ?? 'Assistant'}</div>
            </div>
            <div className="panel-badges">
              <span className="badge">{health?.provider ?? 'backend'}</span>
              <span className="badge">{health?.ok ? 'ready' : 'offline'}</span>
            </div>
          </div>
          <div className="chat-scroll">
            {messages.map((m, idx) => (
              <div className={`chat-item ${m.role}`} key={idx}>
                <div className="chat-role">{m.role}</div>
                <div className="chat-text">{m.text}</div>
                {m.avatar ? <div className="chat-meta">{m.avatar.animation}</div> : null}
              </div>
            ))}
          </div>
          <div className="input-row">
            <input className="chat-input" value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && onSend()} placeholder="Ask the model..." />
            <button className="send-btn" onClick={onSend}>Send</button>
          </div>
        </div>
      )}
    </div>
  )
}
