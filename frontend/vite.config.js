import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://172.28.16.1:8000',
        changeOrigin: true,
        secure: false,
        timeout: 30000,
      },
      '/video': {
        target: 'http://172.28.16.1:8000',
        changeOrigin: true,
        secure: false,
        timeout: 30000,
      },
      '/ws': {
        target: 'ws://172.28.16.1:8000',
        ws: true,
        timeout: 30000,
      },
    },
  },
})
