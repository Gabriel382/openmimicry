import { useEffect, useRef, useState, type CSSProperties, type PointerEvent } from "react";

import { ToolbarIcon } from "../components/ToolbarIcon";
import { useAppearance } from "../hooks/useAppearance";
import { useTauriCommand } from "../hooks/useTauriCommand";
import { useVoiceMode } from "../hooks/useVoiceMode";

type CustomStyle = CSSProperties & Record<`--om-${string}`, string>;

export function ControlsRoute(): JSX.Element {
  const appearance = useAppearance();
  const {
    configureOverlayWindows,
    openBackendDashboard,
    overlayInfo,
    quitApp,
    setPositionLocked,
  } = useTauriCommand();
  const voice = useVoiceMode();
  const controls = appearance.behaviour.controls;
  const [locked, setLocked] = useState(false);
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
      if (info) setLocked(info.position_locked);
    });
  }, [overlayInfo]);

  useEffect(() => {
    return () => {
      if (pointerPtt.current) voice.pttUp();
    };
  }, [voice.pttUp]);

  const beginPtt = (event: PointerEvent<HTMLButtonElement>): void => {
    if ((typeof event.button === "number" && event.button !== 0) || pointerPtt.current) return;
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

  const primaryWakeName =
    voice.wakeNames.find((name) => !name.toLocaleLowerCase().startsWith("hey ")) ??
    voice.wakeNames[0] ??
    "Mimi";

  const style: CustomStyle = {
    "--om-font-family": appearance.theme.font_family,
    "--om-controls-bg": appearance.theme.controls_bg,
    "--om-controls-border": appearance.theme.controls_border,
    "--om-input-bg": appearance.theme.input_bg,
    "--om-input-border": appearance.theme.input_border,
    "--om-accent": appearance.theme.accent,
  };

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
          aria-label={locked ? "Unlock avatar position" : "Lock avatar position"}
          aria-pressed={locked}
          title={locked ? "Unlock avatar position" : "Lock avatar position"}
          onClick={toggleLock}
        >
          <ToolbarIcon name={locked ? "lock" : "unlock"} />
        </button>
        <button
          type="button"
          className="avatar-toolbar__button avatar-toolbar__ptt"
          aria-label="Hold to talk"
          aria-pressed={voice.pttActive}
          title="Hold to talk (or hold Ctrl+Space)"
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
    </div>
  );
}
