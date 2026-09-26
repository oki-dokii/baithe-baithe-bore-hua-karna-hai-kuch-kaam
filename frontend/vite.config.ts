import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target:
          loadEnv(mode, ".", "NWIS_DEV_").NWIS_DEV_API_URL ||
          "http://localhost:8000",
        ws: true,
      },
      "/healthz":
        loadEnv(mode, ".", "NWIS_DEV_").NWIS_DEV_API_URL ||
        "http://localhost:8000",
    },
  },
}));
