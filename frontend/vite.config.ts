import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import Markdown from 'unplugin-vue-markdown/vite'
import { resolve } from 'path'

const proxyTarget = 'http://localhost:35000'

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
    port: 30000,
    proxy: {
      '/api': {
        target: proxyTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '/manage'),
      },
      '/v1/test': {
        target: proxyTarget,
        changeOrigin: true,
      },
      '/v1': {
        target: proxyTarget,
        changeOrigin: true,
      },
      '/health': {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
})
