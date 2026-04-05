
import React, { useEffect, useState } from "react";
import { getConfig, getHealth, postChat } from "../api";

export default function PanelApp() {
  const [config, setConfig] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState("");

  useEffect(() => {
    getConfig().then(setConfig);
    getHealth().then(setHealth);
  }, []);

  async function onSend() {
    const text = input.trim();
    if (!text) return;
    setMessages((prev) => [...prev, { role: "user", text }]);
    setInput("");
    const res = await postChat(text);
    setMessages((prev) => [...prev, { role: "assistant", text: res.text, avatar: res.avatar, backend: res.backend }]);
  }

  if (!config) return <div className="boot">Loading…</div>;

  const colors = config.theme?.colors ?? {};

  return (
    <div className="panel-root" style={{ background: colors.panel_bg, color: colors.text_primary, borderColor: colors.panel_border }}>
      <div className="panel-header">
        <div>
          <div className="panel-title">OpenMimicry</div>
          <div className="panel-subtitle">{config.personality?.name ?? "Assistant"}</div>
        </div>
        <div className="panel-badges">
          <span className="badge">{health?.provider ?? "backend"}</span>
          <span className="badge">{health?.ok ? "ready" : "offline"}</span>
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
        <input className="chat-input" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && onSend()} placeholder="Ask the model..." />
        <button className="send-btn" onClick={onSend}>Send</button>
      </div>
    </div>
  );
}
