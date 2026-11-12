import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the Vite dev server proxies API traffic to the local backend,
// which keeps the browser on a single origin (no CORS preflight needed).
// In production VITE_API_BASE_URL points at the deployed backend instead.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Allow tunnel hostnames (e.g. an HTTPS quick-tunnel demo URL) while the
    // dev server is proxying /api to the local backend.
    allowedHosts: [".trycloudflare.com"],
    proxy: {
      // changeOrigin must stay false so the backend sees the browser's Host and
      // can validate the Origin header (CSRF defence).
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: false },
      "/health": { target: "http://127.0.0.1:8000", changeOrigin: false },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
