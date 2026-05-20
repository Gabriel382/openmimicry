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
      "/api": {
        target: BACKEND_HOST,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      "/ws": {
        target: BACKEND_HOST.replace(/^http/, "ws"),
        ws: true,
        changeOrigin: true,
      },
      "/static": {
        target: BACKEND_HOST,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
