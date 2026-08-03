import { useEffect, useRef, useState, type CSSProperties, type PointerEvent } from "react";

import { ToolbarIcon } from "../components/ToolbarIcon";
import { useAppearance } from "../hooks/useAppearance";
import { useTauriCommand } from "../hooks/useTauriCommand";
import { useRuntimeState } from "../hooks/useRuntimeState";
import { useVoiceMode } from "../hooks/useVoiceMode";

type CustomStyle = CSSProperties & Record<`--om-${string}`, string>;

export function ControlsRoute(): JSX.Element {
  const appearance = useAppearance();
  const {
    configureOverlayWindows,
    openBackendDashboard,
    openBackendDashboardSection,
    overlayInfo,
    quitApp,
    setOverlayInteractive,
    setPositionLocked,
  } = useTauriCommand();
  const voice = useVoiceMode();
  const runtime = useRuntimeState();
  const controls = appearance.behaviour.controls;
  const [locked, setLocked] = useState(false);
  const [overlayInteractive, setOverlayInteractiveState] = useState(false);
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const pointerPtt = useRef(false);

  useEffect(() => {
    void configureOverlayWindows({
      overlayWidth: appearance.windows.overlay.width,
      overlayHeight: appearance.windows.overlay.height,
      controlsWidth: appearance.windows.controls.width,
      controlsHeight: appearance.windows.controls.height,
      composerWidth: appearance.windows.composer.width,
      composerHeight: appearance.windows.composer.height,
      gap: appearance.layout.controls_gap,
      composerGap: appearance.layout.composer_gap,
      alwaysOnTop: appearance.windows.overlay.always_on_top,
      showControls: controls.show,
      showComposer: controls.show_text_input,
    });
  }, [appearance, configureOverlayWindows, controls.show]);

  useEffect(() => {
    void overlayInfo().then((info) => {
      if (info) {
        setLocked(info.position_locked);
        setOverlayInteractiveState(info.interactive);
      }
    });
  }, [overlayInfo]);

  useEffect(() => {
    let cancelled = false;
    const refresh = async (): Promise<void> => {
      try {
        const response = await fetch("/tasks/notifications?unread_only=true");
        if (!response.ok) return;
        const payload = (await response.json()) as { unread?: number };
        if (!cancelled) setUnreadNotifications(Math.max(0, Number(payload.unread) || 0));
      } catch {
        // Backend availability is already surfaced by useRuntimeState.
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    return () => {
      if (pointerPtt.current) voice.pttUp();
    };
  }, [voice.pttUp]);

  const beginPtt = (event: PointerEvent<HTMLButtonElement>): void => {
    if (
      !runtime.canSubmit ||
      (typeof event.button === "number" && event.button !== 0) ||
      pointerPtt.current
    )
      return;
    pointerPtt.current = true;
    if (typeof event.currentTarget.setPointerCapture === "function") {
      event.currentTarget.setPointerCapture(event.pointerId);
    }
    voice.pttDown();
  };

  const endPtt = (): void => {
    if (!pointerPtt.current) return;
    pointerPtt.current = false;
    voice.pttUp();
  };

  const toggleLock = (): void => {
    const next = !locked;
    setLocked(next);
    void setPositionLocked(next);
  };

  const toggleReplyInteraction = (): void => {
    const next = !overlayInteractive;
    setOverlayInteractiveState(next);
    void setOverlayInteractive(next);
  };

  const primaryWakeName =
    voice.wakeNames.find((name) => !name.toLocaleLowerCase().startsWith("hey ")) ??
    voice.wakeNames[0] ??
    "Mimi";

  const pttLabel =
    voice.pttStage === "listening"
      ? "Listening… release to transcribe"
      : voice.pttStage === "transcribing"
        ? "Transcribing…"
        : voice.lastTranscript
          ? `Last heard: ${voice.lastTranscript}`
          : "Hold to talk";

  const style: CustomStyle = {
    "--om-font-family": appearance.theme.font_family,
    "--om-controls-bg": appearance.theme.controls_bg,
    "--om-controls-border": appearance.theme.controls_border,
    "--om-input-bg": appearance.theme.input_bg,
    "--om-input-border": appearance.theme.input_border,
    "--om-accent": appearance.theme.accent,
  };
  const runtimeError =
    runtime.turn?.state === "failed"
      ? runtime.turn.reason || "The current request failed."
      : runtime.runtime?.state === "degraded"
        ? runtime.runtime.reason || "The backend is degraded."
        : runtime.statusLabel === "Backend unavailable"
          ? runtime.statusLabel
          : null;

  return (
    <div className="controls-route" data-route="controls" style={style}>
      <div className="avatar-toolbar" role="toolbar" aria-label="Avatar controls">
        {controls.show_drag_handle && (
          <button
            type="button"
            className="avatar-toolbar__button avatar-toolbar__drag"
            data-tauri-drag-region={locked ? undefined : true}
            disabled={locked}
            aria-label={locked ? "Avatar position locked" : "Drag avatar"}
            title={locked ? "Unlock the avatar before moving it" : "Drag to move the avatar"}
          >
            <ToolbarIcon name="drag" />
          </button>
        )}
        <button
          type="button"
          className="avatar-toolbar__button"
          aria-label={
            unreadNotifications
              ? `Open task notifications (${unreadNotifications} unread)`
              : "Open task notifications"
          }
          title={
            unreadNotifications
              ? `${unreadNotifications} unread task notification${unreadNotifications === 1 ? "" : "s"}`
              : "Open task notifications"
          }
          onClick={() => void openBackendDashboardSection("notifications-section")}
        >
          <ToolbarIcon name="notifications" />
          {unreadNotifications > 0 && (
            <span className="avatar-toolbar__badge" aria-hidden="true">
              {unreadNotifications > 99 ? "99+" : unreadNotifications}
            </span>
          )}
        </button>
        <button
          type="button"
          className="avatar-toolbar__button"
          aria-label={locked ? "Unlock avatar position" : "Lock avatar position"}
          aria-pressed={locked}
          title={locked ? "Unlock avatar position" : "Lock avatar position"}
          onClick={toggleLock}
        >
          <ToolbarIcon name={locked ? "lock" : "unlock"} />
        </button>
        <button
          type="button"
          className="avatar-toolbar__button"
          aria-label={overlayInteractive ? "Disable reply scrolling" : "Enable reply scrolling"}
          aria-pressed={overlayInteractive}
          title={
            overlayInteractive
              ? "Return the avatar to click-through mode"
              : "Interact with and scroll the reply (or press Ctrl+Shift+M)"
          }
          onClick={toggleReplyInteraction}
        >
          <ToolbarIcon name="scroll" />
        </button>
        <button
          type="button"
          className="avatar-toolbar__button avatar-toolbar__ptt"
          data-stage={voice.pttStage}
          disabled={!runtime.canSubmit && !voice.pttActive}
          aria-label={voice.pttStage === "idle" ? "Hold to talk" : pttLabel}
          aria-pressed={voice.pttActive}
          title={`${pttLabel} (or hold Ctrl+Space)`}
          onPointerDown={beginPtt}
          onPointerUp={endPtt}
          onPointerCancel={endPtt}
          onContextMenu={(event) => event.preventDefault()}
        >
          <ToolbarIcon name="microphone" />
        </button>
        <button
          type="button"
          className="avatar-toolbar__button"
          aria-label={`Wake listen ${voice.wakeListening ? "on" : "off"}`}
          aria-pressed={voice.wakeListening}
          title={`Wake listen: ${voice.wakeListening ? "on" : "off"}; say “${primaryWakeName} …” (${voice.sttAdapter})`}
          onClick={voice.toggleWakeListening}
        >
          <ToolbarIcon name="listen" />
        </button>
        <button
          type="button"
          className="avatar-toolbar__button"
          aria-label={`Agent voice ${voice.agentVoice ? "on" : "off"}`}
          aria-pressed={voice.agentVoice}
          title={`Agent voice: ${voice.agentVoice ? "on" : "off"} (${voice.ttsAdapter})`}
          onClick={voice.toggleAgentVoice}
        >
          <ToolbarIcon name="voice" />
        </button>
        <button
          type="button"
          className="avatar-toolbar__button"
          aria-label="Open settings and tasks"
          title="Open settings and tasks in your browser"
          onClick={() => void openBackendDashboard()}
        >
          <ToolbarIcon name="settings" />
        </button>
        <button
          type="button"
          className="avatar-toolbar__button avatar-toolbar__close"
          aria-label="Exit OpenMimicry"
          title="Exit OpenMimicry"
          onClick={() => void quitApp()}
        >
          <ToolbarIcon name="close" />
        </button>
      </div>
      {voice.error && (
        <div className="avatar-toolbar__error" role="alert" title={voice.error}>
          {voice.error}
        </div>
      )}
      {!voice.error && runtimeError && (
        <div className="avatar-toolbar__error" role="alert" title={runtimeError}>
          {runtimeError}
        </div>
      )}
      {!voice.error && !runtimeError && runtime.runtime?.state === "refreshing" && (
        <div
          className="avatar-toolbar__status"
          role="status"
          title={runtime.statusLabel}
        >
          {runtime.statusLabel}
        </div>
      )}
    </div>
  );
}
