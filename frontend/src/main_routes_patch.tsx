
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import OverlayBackground from "./pages/OverlayBackground";
import OverlayAppFull from "./pages/OverlayApp_full";
import PanelApp from "./pages/PanelApp";
import "./styles.css";
import "./styles_overlay_layers.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <Routes>
      <Route path="/" element={<OverlayAppFull />} />
      <Route path="/overlay-ui" element={<OverlayAppFull />} />
      <Route path="/overlay-bg" element={<OverlayBackground />} />
      <Route path="/panel" element={<PanelApp />} />
    </Routes>
  </BrowserRouter>
);
