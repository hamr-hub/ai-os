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

const manageBackend = normalizeTarget(
  process.env.VITE_MANAGE_BACKEND || process.env.VITE_BACKEND || 'http://localhost:35000',
)
const v1Backend = normalizeTarget(process.env.VITE_V1_BACKEND || 'http://localhost:35001')
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
      '/manage': {
        target: manageBackend,
        changeOrigin: true,
      },
      '/api/health/detailed': {
        target: v1Backend,
        changeOrigin: true,
        rewrite: () => '/health/detailed',
      },
      '/api/health': {
        target: v1Backend,
        changeOrigin: true,
        rewrite: () => '/health',
      },
      '/api': {
        target: manageBackend,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '/manage'),
      },
      '/v1': {
        target: v1Backend,
        changeOrigin: true,
      },
      '/health': {
        target: v1Backend,
        changeOrigin: true,
      },
      '/ws': {
        target: manageBackend,
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
