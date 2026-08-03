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

import { useEffect, useState } from "react";

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
  const [route, setRoute] = useState(() => currentRoute());
  useEffect(() => {
    const update = () => setRoute(currentRoute());
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);

  let content: JSX.Element;
  if (route === "/overlay") content = <OverlayRoute />;
  else if (route === "/controls") content = <ControlsRoute />;
  else if (route === "/composer") content = <ComposerRoute />;
  else content = <DashboardRedirect />;

  return (
    <WSProvider>
      <TauriVoiceBridge />
      {content}
    </WSProvider>
  );
}

function currentRoute(): string {
  const value = window.location.hash.replace(/^#/, "").split("?")[0] ?? "/";
  return value.startsWith("/") ? value : "/";
}
