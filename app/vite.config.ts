import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    {
      name: "rufous-public-entry",
      transformIndexHtml: {
        order: "pre",
        handler(html) {
          if (mode !== "public") return html;
          const transformed = html
              .replace('/src/main.tsx', '/src/public-main.tsx')
              .replace('Local evidence-backed birding trip planner', 'Browser-only Arizona bird watch planner with deterministic sunrise calendar events')
              .replace('<title>Rufous</title>', '<title>Rufous · Public Arizona bird watch</title>');
          if (!transformed.includes('/src/public-main.tsx') || transformed.includes('/src/main.tsx')) {
            throw new Error("Public build did not replace the local Rufous entrypoint.");
          }
          return transformed;
        },
      },
    },
  ],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  preview: { host: "127.0.0.1" },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test-setup.ts",
    css: true,
  },
}));
