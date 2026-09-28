import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const nodeEnvironment = globalThis as typeof globalThis & {
  process?: { env?: { XGTEST_WEB_API_TARGET?: string } }
}

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api': nodeEnvironment.process?.env?.XGTEST_WEB_API_TARGET ?? 'http://127.0.0.1:8000',
    },
  },
})
