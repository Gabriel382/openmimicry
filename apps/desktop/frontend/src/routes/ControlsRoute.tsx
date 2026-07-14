import { useEffect, type CSSProperties } from "react";

import { TextInput } from "../components/TextInput";
import { useAppearance } from "../hooks/useAppearance";
import { useTauriCommand } from "../hooks/useTauriCommand";

type CustomStyle = CSSProperties & Record<`--om-${string}`, string>;

export function ControlsRoute(): JSX.Element {
  const appearance = useAppearance();
  const tauri = useTauriCommand();
  const controls = appearance.behaviour.controls;

  useEffect(() => {
    void tauri.configureOverlayWindows({
      overlayWidth: appearance.windows.overlay.width,
      overlayHeight: appearance.windows.overlay.height,
      controlsWidth: appearance.windows.controls.width,
      controlsHeight: appearance.windows.controls.height,
      panelWidth: appearance.windows.panel.width,
      panelHeight: appearance.windows.panel.height,
      gap: appearance.layout.controls_gap,
      alwaysOnTop: appearance.windows.overlay.always_on_top,
      showControls: controls.show,
    });
  }, [appearance, controls.show, tauri]);

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
      {controls.show_drag_handle && (
        <div className="avatar-drag-handle" data-tauri-drag-region>
          <span data-tauri-drag-region aria-hidden="true">⋮⋮</span>
          <span data-tauri-drag-region>{controls.drag_label}</span>
        </div>
      )}
      {controls.show_text_input && (
        <TextInput className="avatar-text-input" placeholder="Message OpenMimicry…" />
      )}
    </div>
  );
}
