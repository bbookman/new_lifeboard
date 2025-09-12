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
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
  server: {
    host: true, // Listen on all interfaces (0.0.0.0)
    https: {
      key: '../127.0.0.1-key.pem',
      cert: '../127.0.0.1.pem'
    },
    proxy: {
      '/api': {
        target: 'https://127.0.0.1:8000',
        changeOrigin: true,
        secure: false, // Accept self-signed certificates
        timeout: 300000,
        proxyTimeout: 300000,
        configure: (proxy, _options) => {
          proxy.on('timeout', () => {
            console.log('API proxy timeout occurred');
          });
          proxy.on('proxyReqWs', (proxyReq, req, socket) => {
            proxyReq.setTimeout(300000);
          });
          proxy.on('proxyRes', (proxyRes, req, res) => {
            proxyRes.setTimeout(300000);
          });
        }
      },
      '/upload': {
        target: 'https://127.0.0.1:8000/api/settings',
        changeOrigin: true,
        secure: false, // Accept self-signed certificates
        timeout: 300000,
        proxyTimeout: 300000,
        configure: (proxy, _options) => {
          proxy.on('timeout', () => {
            console.log('Proxy timeout occurred');
          });
          proxy.on('proxyReqWs', (proxyReq, req, socket) => {
            proxyReq.setTimeout(300000);
          });
          proxy.on('proxyRes', (proxyRes, req, res) => {
            proxyRes.setTimeout(300000);
          });
        }
      },
      '/sync': {
        target: 'https://127.0.0.1:8000',
        changeOrigin: true,
        secure: false, // Accept self-signed certificates
      },
      '/chat': {
        target: 'https://127.0.0.1:8000',
        changeOrigin: true,
        secure: false, // Accept self-signed certificates
      },
      '/calendar': {
        target: 'https://127.0.0.1:8000',
        changeOrigin: true,
        secure: false, // Accept self-signed certificates
      },
      '/embeddings': {
        target: 'https://127.0.0.1:8000',
        changeOrigin: true,
        secure: false, // Accept self-signed certificates
      },
      '/system': {
        target: 'https://127.0.0.1:8000',
        changeOrigin: true,
        secure: false, // Accept self-signed certificates
      },
      '/weather': {
        target: 'https://127.0.0.1:8000',
        changeOrigin: true,
        secure: false, // Accept self-signed certificates
      },
      '/settings': {
        target: 'https://127.0.0.1:8000',
        changeOrigin: true,
        secure: false, // Accept self-signed certificates
      },
      '/headings': {
        target: 'https://127.0.0.1:8000',
        changeOrigin: true,
        secure: false, // Accept self-signed certificates
      },
      '/health': {
        target: 'https://127.0.0.1:8000',
        changeOrigin: true,
        secure: false, // Accept self-signed certificates
      },
      '/debug': {
        target: 'https://127.0.0.1:8000',
        changeOrigin: true,
        secure: false, // Accept self-signed certificates
      }
    }
  }
})
