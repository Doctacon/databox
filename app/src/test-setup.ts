import "@testing-library/jest-dom/vitest";

// MapLibre creates its bundled local worker URL at module load; jsdom omits this browser API.
if (!URL.createObjectURL) Object.defineProperty(URL, "createObjectURL", { value: () => "blob:local-maplibre-worker" });
if (!URL.revokeObjectURL) Object.defineProperty(URL, "revokeObjectURL", { value: () => undefined });
