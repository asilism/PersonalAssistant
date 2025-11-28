import { defineConfig } from 'vite'

export default defineConfig({
  // Development server configuration
  server: {
    port: 5173,
    // Proxy API requests to FastAPI backend
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
    // Watch for file changes
    watch: {
      usePolling: false,
    },
  },

  // Build configuration
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    // Generate source maps for debugging
    sourcemap: true,
  },

  // Resolve configuration
  resolve: {
    alias: {
      '@': '/src',
    },
  },
})
