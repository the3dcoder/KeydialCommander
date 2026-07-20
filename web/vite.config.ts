import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Build the SPA into the Python package so the daemon's ApiServer serves it.
// Dev server proxies the API (incl. the events WebSocket) to the running daemon.
export default defineConfig({
  plugins: [react()],
  base: '/',
  build: {
    outDir: '../src/huion_keydial_mini/web/dist',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8137',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
