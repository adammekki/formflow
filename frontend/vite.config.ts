import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // The backend's CORS default only allows port 3000, so the dev server uses it.
  server: { port: 3000 },
  test: {
    environment: "jsdom",
    setupFiles: "./vitest.setup.ts",
    // Call counts must not leak from one test into the next.
    clearMocks: true,
  },
});
