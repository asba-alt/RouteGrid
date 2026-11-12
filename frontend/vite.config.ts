import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the Vite dev server proxies API traffic to the local backend,
// which keeps the browser on a single origin (no CORS preflight needed).
// In production VITE_API_BASE_URL points at the deployed backend instead.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/health": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
