import React, { useEffect, useMemo, useRef, useState } from "react";
import { getConfig, postChat, postTts } from "../api";
import { speakWithBrowserVoice } from "../browserVoice";
import { closeWindow, minimizeWindow, startWindowDrag } from "../windowApi";

export default function OverlayApp() {
  const [config, setConfig] = useState<any>(null);
  const [currentAnimation, setCurrentAnimation] = useState("idle");
  const [bubbleText, setBubbleText] = useState("");
  const [input, setInput] = useState("");
  const [frameUrl, setFrameUrl] = useState<string | null>(null);
  const [dragEnabled, setDragEnabled] = useState(true);

  const frameTimerRef = useRef<number | null>(null);
  const resetTimerRef = useRef<number | null>(null);

  useEffect(() => {
    getConfig().then(setConfig);
    return () => {
      if (frameTimerRef.current !== null) {
        window.clearInterval(frameTimerRef.current);
      }
      if (resetTimerRef.current !== null) {
        window.clearTimeout(resetTimerRef.current);
      }
    };
  }, []);

  const character = config?.character;
  const theme = config?.theme;
  const colors = theme?.colors ?? {};

  const currentFrames = useMemo(
    () => character?.animations?.[currentAnimation]?.frames ?? [],
    [character, currentAnimation]
  );

  useEffect(() => {
    if (!character?.default_state) return;
    setCurrentAnimation(character.default_state);
  }, [character]);

  useEffect(() => {
    if (frameTimerRef.current !== null) {
      window.clearInterval(frameTimerRef.current);
      frameTimerRef.current = null;
    }

    if (!currentFrames.length) {
      setFrameUrl(null);
      return;
    }

    let index = 0;
    setFrameUrl(`http://localhost:8000/static/${currentFrames[0]}`);

    const fps = character?.animations?.[currentAnimation]?.fps ?? 6;
    frameTimerRef.current = window.setInterval(() => {
      index = (index + 1) % currentFrames.length;
      setFrameUrl(`http://localhost:8000/static/${currentFrames[index]}`);
    }, Math.max(80, Math.floor(1000 / fps)));

    return () => {
      if (frameTimerRef.current !== null) {
        window.clearInterval(frameTimerRef.current);
        frameTimerRef.current = null;
      }
    };
  }, [currentFrames, currentAnimation, character]);

  async function onSend() {
    const text = input.trim();
    if (!text) return;

    if (resetTimerRef.current !== null) {
      window.clearTimeout(resetTimerRef.current);
      resetTimerRef.current = null;
    }

    setInput("");
    setCurrentAnimation(character?.thinking_animation ?? "thinking");
    setBubbleText("Thinking...");

    const res = await postChat(text);

    setBubbleText(res.text);
    setCurrentAnimation(res.avatar.animation);

    const spoke = speakWithBrowserVoice(res.text);
    if (!spoke) {
      await postTts(res.text);
    }

    resetTimerRef.current = window.setTimeout(() => {
      setCurrentAnimation(res.avatar.next_state || "idle");
      setBubbleText("");
      resetTimerRef.current = null;
    }, 2500);
  }

  async function onDragMouseDown(
    e: React.MouseEvent<HTMLButtonElement>
  ) {
    if (!dragEnabled) return;
    e.preventDefault();
    await startWindowDrag();
  }

  if (!config) return <div className="boot">Loading…</div>;

  return (
    <div className="overlay-root">
      <div className="topbar">
        <div className="title">OpenMimicry</div>

        <button
          className={`drag-handle ${dragEnabled ? "active" : "inactive"}`}
          onMouseDown={onDragMouseDown}
          title={dragEnabled ? "Click and drag window" : "Dragging locked"}
        >
          ⠿ Drag
        </button>

        <div className="window-buttons">
          <button
            className="control-btn"
            onClick={() => setDragEnabled((v) => !v)}
            title={dragEnabled ? "Lock movement" : "Enable dragging"}
          >
            {dragEnabled ? "Lock" : "Unlock"}
          </button>
          <button className="control-btn" onClick={minimizeWindow}>—</button>
          <button className="control-btn close-btn" onClick={closeWindow}>✕</button>
        </div>
      </div>

      {bubbleText ? (
        <div
          className="bubble"
          style={{ background: colors.bubble_bg, color: colors.bubble_text }}
        >
          {bubbleText}
        </div>
      ) : null}

      <div className="avatar-stage">
        {frameUrl ? (
          <img src={frameUrl} className="avatar-image" alt={currentAnimation} />
        ) : null}
      </div>

      <div className="state-badge">{currentAnimation}</div>

      <div
        className="input-dock"
        style={{ background: colors.dock_bg, borderColor: colors.dock_border }}
      >
        <input
          className="dock-input"
          style={{
            background: colors.input_bg,
            borderColor: colors.input_border,
            color: colors.text_primary
          }}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSend()}
          placeholder="Ask the model..."
        />
        <button className="send-btn" onClick={onSend}>Send</button>
      </div>
    </div>
  );
}