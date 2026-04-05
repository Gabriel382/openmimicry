import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import OverlayApp from "./pages/OverlayApp";
import PanelApp from "./pages/PanelApp";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <Routes>
      <Route path="/" element={<OverlayApp />} />
      <Route path="/overlay" element={<OverlayApp />} />
      <Route path="/panel" element={<PanelApp />} />
    </Routes>
  </BrowserRouter>
);