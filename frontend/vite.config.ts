import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import Markdown from 'unplugin-vue-markdown/vite'
import { resolve } from 'path'

const backend = process.env.VITE_BACKEND || 'http://localhost:35000'

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
        target: backend,
        changeOrigin: true,
      },
      '/api': {
        target: backend,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '/manage'),
      },
      '/v1': {
        target: backend,
        changeOrigin: true,
      },
      '/health': {
        target: backend,
        changeOrigin: true,
      },
      '/ws': {
        target: backend,
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
