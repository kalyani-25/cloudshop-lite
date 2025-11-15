import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // proxy API calls from Vite dev server (5173) to Nginx (80)
      '/users': {
        target: 'http://localhost',
        changeOrigin: true,
      },
      '/catalog': {
        target: 'http://localhost',
        changeOrigin: true,
      },
      '/orders': {
        target: 'http://localhost',
        changeOrigin: true,
      },
    },
  },
})

