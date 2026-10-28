import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // The build a page was loaded from, sent with every request (src/api.js) so a bug report
  // shows which version it came from. Railway sets the commit during its build.
  define: {
    "import.meta.env.VITE_BUILD": JSON.stringify(process.env.VITE_BUILD || (process.env.RAILWAY_GIT_COMMIT_SHA || "").slice(0, 7)),
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/food": "http://127.0.0.1:8000",
      "/tastelab": "http://127.0.0.1:8000",
      "/admin": "http://127.0.0.1:8000",
    },
  },
});
