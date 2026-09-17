import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // The frontend calls fetch("/api/..."); forward that to the FastAPI
      // backend during `npm run dev` (see backend/README.md). Only used by
      // the dev server itself, not by the browser -- set
      // VITE_API_PROXY_TARGET if the backend isn't on localhost:8000.
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
