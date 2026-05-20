/**
 * `<SettingsPanel />` — pack + runtime swap controls.
 *
 * Talks to the backend over HTTP (POST /pack/swap, /runtime/swap). The
 * backend M6 routes return JSON; we surface failures inline.
 */

import { useCallback, useState } from "react";

import { runtimeRegistry } from "../runtimes/registry";

const DEFAULT_PACKS = ["octomimic"];

export interface SettingsPanelProps {
  /** Optional override for the available pack list (UI dropdown only). */
  availablePacks?: string[];
  className?: string;
  /** Pluggable fetch (tests inject a stub). */
  fetcher?: typeof fetch;
}

export function SettingsPanel(props: SettingsPanelProps): JSX.Element {
  const fetcher = props.fetcher ?? fetch;
  const [pack, setPack] = useState<string>(props.availablePacks?.[0] ?? "octomimic");
  const [runtime, setRuntime] = useState<string>("sprite2d");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<boolean>(false);

  const swap = useCallback(
    async (kind: "pack" | "runtime", value: string): Promise<void> => {
      setBusy(true);
      setError(null);
      try {
        const path = kind === "pack" ? "/pack/swap" : "/runtime/swap";
        const body = kind === "pack" ? { pack: value } : { runtime: value };
        const res = await fetcher(path, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const detail = await res.text().catch(() => "");
          setError(`${path} ${res.status}: ${detail || res.statusText}`);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    },
    [fetcher],
  );

  const packs = props.availablePacks ?? DEFAULT_PACKS;
  const runtimes = Object.keys(runtimeRegistry);

  return (
    <div className={`settings-panel ${props.className ?? ""}`}>
      <label className="settings-panel__field">
        <span>Character pack</span>
        <select value={pack} onChange={(e) => setPack(e.target.value)} disabled={busy}>
          {packs.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <button type="button" disabled={busy} onClick={() => void swap("pack", pack)}>
          Swap pack
        </button>
      </label>

      <label className="settings-panel__field">
        <span>Avatar runtime</span>
        <select
          value={runtime}
          onChange={(e) => setRuntime(e.target.value)}
          disabled={busy}
        >
          {runtimes.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <button type="button" disabled={busy} onClick={() => void swap("runtime", runtime)}>
          Swap runtime
        </button>
      </label>

      {error && (
        <p className="settings-panel__error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
