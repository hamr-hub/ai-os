import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import Markdown from 'unplugin-vue-markdown/vite'
import { resolve } from 'path'

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
      '/api/manage': {
        target: 'http://ssh.hamr.top:27145',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/api': {
        target: 'http://ssh.hamr.top:27145',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '/manage'),
      },
      '/v1/test': {
        target: 'http://ssh.hamr.top:27145',
        changeOrigin: true,
      },
      '/v1': {
        target: 'http://ssh.hamr.top:27145',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://ssh.hamr.top:27145',
        changeOrigin: true,
      },
    },
  },
})
