/**
 * App shell. Routes:
 *
 * - `/overlay` — transparent avatar host (Tauri overlay window).
 * - `/panel`   — interactive UI (Tauri panel window).
 * - `/`        — redirects to `/panel` as a sensible browser default.
 *
 * Both routes share the same `WSProvider`, so the overlay reflects state
 * the panel drives.
 */

import { HashRouter, Navigate, Route, Routes } from "react-router-dom";

import { OverlayRoute } from "./routes/OverlayRoute";
import { PanelRoute } from "./routes/PanelRoute";
import { ControlsRoute } from "./routes/ControlsRoute";
import { WSProvider } from "./ws/WSProvider";
import { TauriVoiceBridge } from "./components/TauriVoiceBridge";

export function App(): JSX.Element {
  return (
    <WSProvider>
      <TauriVoiceBridge />
      <HashRouter>
        <Routes>
          <Route path="/overlay" element={<OverlayRoute />} />
          <Route path="/controls" element={<ControlsRoute />} />
          <Route path="/panel" element={<PanelRoute />} />
          <Route path="/" element={<Navigate to="/panel" replace />} />
          <Route path="*" element={<Navigate to="/panel" replace />} />
        </Routes>
      </HashRouter>
    </WSProvider>
  );
}
