import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Backend defaults to localhost:8000 (M6). Tauri/desktop production
// builds bypass the proxy because both processes live on localhost
// already; dev needs the proxy so the browser-served frontend can talk
// to the FastAPI process without CORS pain.
const BACKEND_HOST = process.env["OPENMIMICRY_BACKEND_HOST"] ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    proxy: {
      // Generic `/api/...` rewrite path (left in for callers that
      // prefer prefixed URLs).
      "/api": {
        target: BACKEND_HOST,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      // WebSocket bridge to the M6 backend.
      "/ws": {
        target: BACKEND_HOST.replace(/^http/, "ws"),
        ws: true,
        changeOrigin: true,
      },
      // Static character assets (sprite frames, VRM meshes).
      "/static": {
        target: BACKEND_HOST,
        changeOrigin: true,
      },
      // Bare backend routes — let the frontend fetch them without the
      // `/api/` prefix. Mirrors `apps/backend/.../routes/*.py`.
      "/chat": { target: BACKEND_HOST, changeOrigin: true },
      "/health": { target: BACKEND_HOST, changeOrigin: true },
      "/mode": { target: BACKEND_HOST, changeOrigin: true },
      "/pack": { target: BACKEND_HOST, changeOrigin: true },
      "/runtime": { target: BACKEND_HOST, changeOrigin: true },
      "/admin": { target: BACKEND_HOST, changeOrigin: true },
      "/config": { target: BACKEND_HOST, changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
