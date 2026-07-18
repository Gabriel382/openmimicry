/**
 * App shell. Routes:
 *
 * - `/overlay` — transparent avatar host (Tauri overlay window).
 * - `/controls` — interactive toolbar docked above the avatar.
 * - `/composer` — message field docked underneath the avatar.
 * - `/`         — redirects to the browser-hosted backend dashboard.
 *
 * The avatar and toolbar share one `WSProvider`; settings and tasks live in
 * the backend-hosted browser dashboard.
 */

import { useEffect } from "react";
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";

import { OverlayRoute } from "./routes/OverlayRoute";
import { ControlsRoute } from "./routes/ControlsRoute";
import { ComposerRoute } from "./routes/ComposerRoute";
import { WSProvider } from "./ws/WSProvider";
import { TauriVoiceBridge } from "./components/TauriVoiceBridge";

function DashboardRedirect(): JSX.Element {
  useEffect(() => {
    window.location.replace("http://127.0.0.1:8000/dashboard");
  }, []);
  return <p>Opening the OpenMimicry dashboard…</p>;
}

export function App(): JSX.Element {
  return (
    <WSProvider>
      <TauriVoiceBridge />
      <HashRouter>
        <Routes>
          <Route path="/overlay" element={<OverlayRoute />} />
          <Route path="/controls" element={<ControlsRoute />} />
          <Route path="/composer" element={<ComposerRoute />} />
          <Route path="/dashboard" element={<DashboardRedirect />} />
          <Route path="/panel" element={<Navigate to="/dashboard" replace />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </HashRouter>
    </WSProvider>
  );
}
