import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import Markdown from 'unplugin-vue-markdown/vite'
import { resolve } from 'path'

const manageBackend = process.env.VITE_MANAGE_BACKEND || process.env.VITE_BACKEND || 'http://localhost:35000'
const v1Backend = process.env.VITE_V1_BACKEND || 'http://localhost:35001'

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
  server: {
    host: '0.0.0.0',
    port: 30001,
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
