import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Native file events are missed on some Windows setups; polling keeps hot reload reliable.
    watch: { usePolling: true, interval: 300 },
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
