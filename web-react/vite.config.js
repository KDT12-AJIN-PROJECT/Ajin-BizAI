import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import dotenv from 'dotenv'
import path from 'path'
import { fileURLToPath } from 'url'

// .env.server 에서 서버 전용 토큰/키 로딩 (브라우저 미노출, proxy에서만 사용)
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const envServer = dotenv.config({ path: path.resolve(__dirname, '.env.server') }).parsed || {}
const LM_STUDIO_TOKEN = envServer.LM_STUDIO_TOKEN || process.env.LM_STUDIO_TOKEN || ''
const LM_STUDIO_TARGET = envServer.LM_STUDIO_URL || 'http://127.0.0.1:1234'

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: ['www.student-mac.com'],
    proxy: {
      // 기업마당 API
      '/proxy/bizinfo': {
        target: 'https://www.bizinfo.go.kr',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/proxy\/bizinfo/, ''),
      },
      // 공공데이터포털 API
      '/proxy/apis': {
        target: 'https://apis.data.go.kr',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/proxy\/apis/, ''),
      },
      // ✅ 기업마당 첨부파일 (신규 추가)
      '/proxy/bizfiles': {
        target: 'https://www.bizinfo.go.kr',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/proxy\/bizfiles/, ''),
      },
      // ✅ K-Startup/공공데이터 첨부파일 (신규 추가)
      '/proxy/kstartupfiles': {
        target: 'https://www.k-startup.go.kr',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/proxy\/kstartupfiles/, ''),
      },
      // LM Studio (server.js 와 동일하게 .env.server 의 LM_STUDIO_TOKEN 자동 주입)
      '/proxy/lmstudio': {
        target: LM_STUDIO_TARGET,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/proxy\/lmstudio/, ''),
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            if (LM_STUDIO_TOKEN) {
              proxyReq.setHeader('Authorization', `Bearer ${LM_STUDIO_TOKEN}`)
            }
          })
        },
      },
      // Python 백엔드 전체 (/api/* → FastAPI:8000)
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
