/** Vite entry. Mounts `<App />` into `#root`. */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import "./styles/overlay.css";
import "./styles/panel.css";

const container = document.getElementById("root");
if (!container) {
  throw new Error("openmimicry-frontend: missing #root in index.html");
}
createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
