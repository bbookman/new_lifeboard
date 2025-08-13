import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/upload': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/sync': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/chat': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/calendar': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/embeddings': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/system': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/weather': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/settings': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/headings': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
