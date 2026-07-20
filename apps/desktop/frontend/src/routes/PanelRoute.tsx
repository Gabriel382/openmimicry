/**
 * `/panel` — the interactive UI: text input, task feed, voice toggles,
 * settings.
 */

import type { CSSProperties } from "react";

import { ModeIndicator } from "../components/ModeIndicator";
import { SettingsPanel } from "../components/SettingsPanel";
import { TaskCard } from "../components/TaskCard";
import { TextInput } from "../components/TextInput";
import { VoiceToggle } from "../components/VoiceToggle";
import { useAppearance } from "../hooks/useAppearance";
import { useRuntimeState } from "../hooks/useRuntimeState";

type CustomStyle = CSSProperties & Record<`--om-${string}`, string>;

export function PanelRoute(): JSX.Element {
  const appearance = useAppearance();
  const runtime = useRuntimeState();
  const style: CustomStyle = {
    "--om-panel-bg": appearance.theme.panel_bg,
    "--om-panel-text": appearance.theme.panel_text,
    "--om-accent": appearance.theme.accent,
    "--om-font-family": appearance.theme.font_family,
  };
  return (
    <div className="panel-route" data-route="panel" style={style}>
      <header className="panel-route__header">
        <ModeIndicator />
      </header>
      <main className="panel-route__main">
        <section className="panel-route__chat">
          <TextInput
            autoFocus
            disabled={!runtime.canSubmit}
            placeholder={runtime.canSubmit ? "Talk to me..." : runtime.statusLabel}
          />
        </section>
        <section className="panel-route__voice">
          <VoiceToggle />
        </section>
        <section className="panel-route__tasks">
          <h2>Tasks</h2>
          <TaskCard />
        </section>
        <section className="panel-route__settings">
          <h2>Settings</h2>
          <SettingsPanel />
        </section>
      </main>
    </div>
  );
}
