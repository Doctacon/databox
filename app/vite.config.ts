import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const PUBLIC_ASSET_GENERATION = "g2";

function publicAlias(source: string) {
  return `/src/publicAdapters/${source}`;
}

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
  resolve: {
    alias: mode === "public" ? [
      { find: "./api", replacement: publicAlias("tripApi.ts") },
      { find: "./birdApi", replacement: publicAlias("birdApi.ts") },
      { find: "./mapApi", replacement: publicAlias("mapApi.ts") },
      { find: "./collectionApi", replacement: publicAlias("collectionApi.ts") },
      { find: "./targetApi", replacement: publicAlias("targetApi.ts") },
      { find: "./alertDeliveryApi", replacement: publicAlias("alertDeliveryApi.ts") },
      { find: "./SourceRefreshControl", replacement: publicAlias("SourceRefreshControl.tsx") },
      { find: "./TripCalendarControls", replacement: publicAlias("TripCalendarControls.tsx") },
    ] : [],
  },
  build: mode === "public" ? {
    rollupOptions: {
      output: {
        entryFileNames: `assets/[name]-${PUBLIC_ASSET_GENERATION}-[hash].js`,
        chunkFileNames: `assets/[name]-${PUBLIC_ASSET_GENERATION}-[hash].js`,
        assetFileNames: `assets/[name]-${PUBLIC_ASSET_GENERATION}-[hash][extname]`,
      },
    },
  } : undefined,
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
