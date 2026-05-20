/**
 * `/panel` — the interactive UI: text input, task feed, voice toggles,
 * settings.
 */

import { ModeIndicator } from "../components/ModeIndicator";
import { SettingsPanel } from "../components/SettingsPanel";
import { TaskCard } from "../components/TaskCard";
import { TextInput } from "../components/TextInput";
import { VoiceToggle } from "../components/VoiceToggle";

export function PanelRoute(): JSX.Element {
  return (
    <div className="panel-route" data-route="panel">
      <header className="panel-route__header">
        <ModeIndicator />
      </header>
      <main className="panel-route__main">
        <section className="panel-route__chat">
          <TextInput autoFocus />
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
