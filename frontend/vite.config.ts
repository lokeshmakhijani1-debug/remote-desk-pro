import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({plugins:[react(),tailwindcss()],optimizeDeps:{exclude:["@bokuweb/zstd-wasm"],esbuildOptions:{target:"es2020"}}});
