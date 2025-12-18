import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // listen on all interfaces
    port: 5173, // sandbox port
    allowedHosts: [
      '5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai',
      'ecg8sggokso8g00o8okoc8sc.18.143.160.131.sslip.io',
      'localhost',
      '.sandbox.novita.ai', // Allow all sandbox domains
    ],
    proxy: {
      // Proxy API requests to Flask backend during development
      '/api': {
        target: 'http://localhost:5050',
        changeOrigin: true,
        secure: false,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('proxy error', err);
          });
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log('Sending Request to the Target:', req.method, req.url);
          });
          proxy.on('proxyRes', (proxyRes, req, _res) => {
            console.log('Received Response from the Target:', proxyRes.statusCode, req.url);
          });
        },
      },
      '/login': {
        target: 'http://localhost:5050',
        changeOrigin: true,
        secure: false,
      },
      '/logout': {
        target: 'http://localhost:5050',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})
