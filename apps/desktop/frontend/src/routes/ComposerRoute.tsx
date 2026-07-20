import type { CSSProperties } from "react";

import { TextInput } from "../components/TextInput";
import { useAppearance } from "../hooks/useAppearance";
import { useRuntimeState } from "../hooks/useRuntimeState";

type CustomStyle = CSSProperties & Record<`--om-${string}`, string>;

/** Interactive message composer docked underneath the click-through avatar. */
export function ComposerRoute(): JSX.Element {
  const appearance = useAppearance();
  const runtime = useRuntimeState();
  const style: CustomStyle = {
    "--om-font-family": appearance.theme.font_family,
    "--om-controls-bg": appearance.theme.controls_bg,
    "--om-controls-border": appearance.theme.controls_border,
    "--om-input-bg": appearance.theme.input_bg,
    "--om-input-border": appearance.theme.input_border,
    "--om-accent": appearance.theme.accent,
  };

  return (
    <div className="composer-route" data-route="composer" style={style}>
      <TextInput
        className="avatar-text-input"
        placeholder={runtime.canSubmit ? "Message OpenMimicry…" : runtime.statusLabel}
        disabled={!runtime.canSubmit}
      />
    </div>
  );
}
