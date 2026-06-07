import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Le port est aligné sur FRONTEND_PORT (5173). `host` ouvre le serveur dev sur
// l'interface du conteneur ; la publication reste bornée à 127.0.0.1 via compose.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.js"],
  },
});
