import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

// Dev-only mock API. Enabled by VITE_MOCK=1. Intercepts fetch("/api/...") calls
// at the dev-server middleware level so the frontend can be built and tested
// before the FastAPI service exists. Never bundled into the production
// build: the plugin itself only registers a `configureServer` hook, which
// Vite runs for `vite dev` / `vite preview`, not for `vite build`, and the
// handler module is imported dynamically so it is never pulled into the
// production JS bundle either.
function mockApiPlugin(): Plugin {
  return {
    name: "chorus-mock-api",
    apply: "serve",
    configureServer(server) {
      if (process.env.VITE_MOCK !== "1") return;
      server.middlewares.use(async (req, res, next) => {
        if (!req.url || !req.url.startsWith("/api/")) return next();
        const { handleMockRequest } = await import("./src/mock/server.ts");
        const handled = await handleMockRequest(req, res);
        if (!handled) next();
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), mockApiPlugin()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
  },
  test: {
    environment: "node",
    globals: true,
  },
});
