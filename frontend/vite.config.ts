import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            charts: ["recharts"],
          },
        },
      },
    },
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/ai-local": {
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/ai-local/, ""),
          target: environment.AI_SERVICE_DEV_URL || "http://127.0.0.1:8000",
        },
      },
    },
  };
});
