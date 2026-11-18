import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1", // never expose the lab UI on the network
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", ws: true } },
  },
});
