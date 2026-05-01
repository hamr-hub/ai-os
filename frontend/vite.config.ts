import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import Markdown from 'unplugin-vue-markdown/vite'
import { resolve } from 'path'

const normalizeTarget = (value: string) => value.trim().replace(/\/+$/, '')
const resolvePort = (value: string | undefined, fallback: number) => {
  const parsed = Number.parseInt(value ?? '', 10)
  return Number.isFinite(parsed) ? parsed : fallback
}

const unifiedBackend = normalizeTarget(
  process.env.VITE_BACKEND || 'http://localhost:35000',
)
const gatewayBackend = normalizeTarget(
  process.env.VITE_GATEWAY || 'http://localhost:35001',
)
const devServerPort = resolvePort(process.env.VITE_PORT || process.env.PORT, 30001)

export default defineConfig({
  plugins: [
    vue({
      include: [/\.vue$/, /\.md$/],
    }),
    Markdown({
      wrapperClasses: 'markdown-body',
    }),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  build: {
    target: 'es2020',
    sourcemap: false,
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          'chart': ['chart.js', 'vue-chartjs'],
          'markdown': ['marked', 'dompurify', 'highlight.js/lib/core'],
          'ui-icons': ['lucide-vue-next'],
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: devServerPort,
    strictPort: true,
    proxy: {
      '/api/health/detailed': {
        target: unifiedBackend,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/api/health/alert': {
        target: unifiedBackend,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '/manage'),
      },
      '/api/health/history': {
        target: unifiedBackend,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '/manage'),
      },
      '/api/health': {
        target: gatewayBackend,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/manage': {
        target: unifiedBackend,
        changeOrigin: true,
      },
      '/api': {
        target: unifiedBackend,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '/manage'),
      },
      '/v1': {
        target: gatewayBackend,
        changeOrigin: true,
      },
      '/health': {
        target: gatewayBackend,
        changeOrigin: true,
      },
      '/ws': {
        target: unifiedBackend,
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
