import express from 'express'
import { createProxyMiddleware } from 'http-proxy-middleware'
import dotenv from 'dotenv'
import path from 'path'
import { fileURLToPath } from 'url'

dotenv.config({ path: new URL('.env.server', import.meta.url).pathname })

const app = express()
const __dirname = path.dirname(fileURLToPath(import.meta.url))

const API_KEY   = process.env.API_KEY
const BIZ_KEY   = process.env.BIZ_KEY
const LM_TOKEN  = process.env.LM_STUDIO_TOKEN
const LM_URL    = process.env.LM_STUDIO_URL || 'http://127.0.0.1:1234'
const PORT      = process.env.PORT || 3000

// ── 정적 파일 (React 빌드 결과물) ──────────────────────────────
app.use(express.static(path.join(__dirname, 'dist')))

// ── API 진단 엔드포인트 (/api/test) ────────────────────────────
// 브라우저에서 http://localhost:3000/api/test 접속하면 각 API 상태 확인 가능
app.get('/api/test', async (_req, res) => {
  const tests = [
    {
      name: '기업마당(bizinfo)',
      url: `https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do?dataType=json&searchNm=%EC%9E%90%EB%8F%99%EC%B0%A8&sortId=L&crtfcKey=${BIZ_KEY}`,
    },
    {
      name: '과기부(msit)',
      url: `https://apis.data.go.kr/1721000/msitannouncementinfo/businessAnnouncMentList?pageNo=1&numOfRows=3&returnType=json&ServiceKey=${API_KEY}`,
    },
    {
      name: '중기부(mss)',
      url: `https://apis.data.go.kr/1421000/mssBizService_v2/getbizList_v2?pageNo=1&numOfRows=3&serviceKey=${API_KEY}`,
    },
    {
      name: '창진원(kstartup)',
      url: `https://apis.data.go.kr/B552735/kisedKstartupService01/getBusinessInformation01?page=1&perPage=3&returnType=json&serviceKey=${API_KEY}`,
    },
  ]

  const results = {}
  for (const t of tests) {
    try {
      const r = await fetch(t.url, { signal: AbortSignal.timeout(10000) })
      const text = await r.text()
      results[t.name] = {
        status: r.status,
        ok: r.ok,
        url: t.url.replace(API_KEY ?? '', '***').replace(BIZ_KEY ?? '', '***'),
        preview: text.slice(0, 400),
      }
    } catch (e) {
      results[t.name] = { error: e.message, url: t.url.replace(API_KEY ?? '', '***').replace(BIZ_KEY ?? '', '***') }
    }
  }

  res.json({
    keys: {
      API_KEY: API_KEY ? `${API_KEY.slice(0, 8)}...` : '(없음 — .env.server 확인)',
      BIZ_KEY: BIZ_KEY ? `${BIZ_KEY.slice(0, 4)}...` : '(없음 — .env.server 확인)',
    },
    results,
  })
})

// ── 기업마당 API (/proxy/bizinfo) ──────────────────────────────
// on.proxyReq 방식: http-proxy-middleware v3 권장 방법
app.use('/proxy/bizinfo', createProxyMiddleware({
  target: 'https://www.bizinfo.go.kr',
  changeOrigin: true,
  pathRewrite: { '^/proxy/bizinfo': '' },
  on: {
    proxyReq: (proxyReq) => {
      // proxyReq.path 에 API 키 추가
      const sep = proxyReq.path.includes('?') ? '&' : '?'
      proxyReq.path += `${sep}crtfcKey=${BIZ_KEY}`
    },
  },
}))

// ── 공공데이터포털 API (/proxy/apis) ───────────────────────────
// 과기부는 ServiceKey, 중기부·창진원은 serviceKey — 둘 다 붙여도 무관
app.use('/proxy/apis', createProxyMiddleware({
  target: 'https://apis.data.go.kr',
  changeOrigin: true,
  pathRewrite: { '^/proxy/apis': '' },
  on: {
    proxyReq: (proxyReq) => {
      const sep = proxyReq.path.includes('?') ? '&' : '?'
      proxyReq.path += `${sep}ServiceKey=${API_KEY}&serviceKey=${API_KEY}`
    },
  },
}))

// ── LM Studio (/proxy/lmstudio) ────────────────────────────────
app.use('/proxy/lmstudio', createProxyMiddleware({
  target: LM_URL,
  changeOrigin: true,
  pathRewrite: { '^/proxy/lmstudio': '' },
  on: {
    proxyReq: (proxyReq) => {
      if (LM_TOKEN) proxyReq.setHeader('Authorization', `Bearer ${LM_TOKEN}`)
    },
  },
}))

// ── Python 백엔드 전체 (/api/* → FastAPI:8000) ─────────────────
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'
app.use('/api', createProxyMiddleware({ target: BACKEND_URL, changeOrigin: true }))

// ── SPA fallback ───────────────────────────────────────────────
app.get('*', (_req, res) => {
  res.sendFile(path.join(__dirname, 'dist', 'index.html'))
})

app.listen(PORT, () => {
  console.log(`✅ Server running on http://localhost:${PORT}`)
  console.log(`   API_KEY : ${API_KEY ? API_KEY.slice(0, 8) + '...' : '⚠️  (없음)'}`)
  console.log(`   BIZ_KEY : ${BIZ_KEY ? BIZ_KEY.slice(0, 4) + '...' : '⚠️  (없음)'}`)
  console.log(`   진단    : http://localhost:${PORT}/api/test`)
})
