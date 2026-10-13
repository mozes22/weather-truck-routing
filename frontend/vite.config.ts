import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    // In development, requests to /api go to Django. This avoids CORS problems.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
});
