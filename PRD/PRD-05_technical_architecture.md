# PRD-05: 기술 아키텍처 (Technical Architecture)

> **문서 버전** 1.0 | **선행 문서** PRD-04 | **후행 문서** PRD-06  
> **목적** 기술 스택, 환경 설정, 디렉토리 구조의 완전한 명세

---

## 1. 시스템 아키텍처 다이어그램

```
┌──────────────────────────────────────────────────────────────────┐
│                       클라이언트 (Browser)                        │
│                                                                    │
│  React 18 + Vite 5 + TailwindCSS 3 + shadcn/ui                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │  공고 검색    │ │  초안 작성    │ │  설정/이력    │             │
│  │  (MainPage)  │ │ (ChatDraft)  │ │  (Settings)  │             │
│  └──────┬───────┘ └──────┬───────┘ └──────────────┘             │
│         │                │                                         │
└─────────┼────────────────┼─────────────────────────────────────-─┘
          │ HTTP/CORS 프록시│ HTTP
          ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   미들웨어 (Node.js Express)                      │
│                   web-react/server.js                             │
│   역할: API 키 보호, CORS 처리, 공공 API 프록시                    │
│   포트: 3001                                                      │
└──────────────┬──────────────────────────────────────────────────┘
               │
     ┌─────────┼─────────────────────┐
     ▼         ▼                     ▼
┌─────────┐ ┌────────────┐ ┌──────────────────┐
│공공 API  │ │  LLM API   │ │ Python Backend   │
│기업마당  │ │LM Studio   │ │ FastAPI (포트:   │
│중기부   │ │OpenAI      │ │ 8000)            │
│과기부   │ │Anthropic   │ │ 파일 파싱,       │
│창진원   │ └────────────┘ │ AI 진단          │
└─────────┘               └──────────────────┘
```

---

## 2. 기술 스택 (버전 고정)

| 레이어 | 기술 | 버전 | 선택 이유 |
|--------|------|------|---------|
| **UI** | React | 18.3.1 | 기존 코드베이스, 상태관리 단순 |
| **빌드** | Vite | 5.4.2 | 빠른 HMR, ES Module 기반 |
| **스타일** | TailwindCSS | 3.4.14 | 유틸리티 클래스, shadcn/ui 필수 |
| **UI 컴포넌트** | shadcn/ui | 2024-11 기준 | 기존 코드 사용 중 |
| **아이콘** | lucide-react | 0.454.0 | 기존 코드 사용 중 |
| **프록시** | Express | 4.21.1 | 경량, API 키 보호 |
| **백엔드** | FastAPI | 0.115.4 | Python 생태계, 비동기 |
| **WSGI** | uvicorn | 0.32.0 | FastAPI 표준 |
| **PDF 파싱** | pdfplumber | 0.11.4 | 한국어 PDF 지원 |
| **DOCX** | python-docx | 1.1.2 | 표준 라이브러리 |
| **임베딩** | sentence-transformers | 3.3.1 | 한국어 모델 지원 |
| **컨테이너** | Docker | 26.x | 표준 배포 환경 |

---

## 3. 환경변수 완전 명세

### 3.1 프론트엔드 (.env)

```bash
# web-react/.env.example — 이 파일을 복사하여 .env 생성

# ── 백엔드 프록시 ──────────────────────────────────────────────────
VITE_API_BASE_URL=http://localhost:3001

# ── LLM ──────────────────────────────────────────────────────────
# 우선순위: OPENAI > ANTHROPIC > LM Studio (순서대로 체크)
VITE_LM_STUDIO_URL=http://localhost:1234/v1
VITE_OPENAI_API_KEY=                         # 입력하면 OpenAI 우선 사용
VITE_ANTHROPIC_API_KEY=                      # 입력하면 Anthropic 사용

# ── 공공 API ──────────────────────────────────────────────────────
VITE_BIZINFO_API_URL=https://www.bizinfo.go.kr/cm/search/searchList.do
VITE_MSIT_API_URL=https://www.msit.go.kr/publicinfo/bbs/view.do
VITE_MSS_API_URL=https://www.mss.go.kr/site/smba/foffice/ex/bslsptTarget/findBslsptTargetList.do
VITE_KSTARTUP_API_URL=https://apis.data.go.kr/B552735/kisedKstartup/getAnnouncedNotices

# ── API 인증 ──────────────────────────────────────────────────────
VITE_BIZ_KEY=                                # 기업마당 API 키 (필수)
VITE_API_KEY=                                # 공공데이터포털 API 키 (필수)
VITE_NOTICE_SEARCH_NM=자동차 부품             # 기업마당 검색어 기본값

# ── 앱 동작 ──────────────────────────────────────────────────────
VITE_USE_MOCK_WHEN_FAILED=true               # API 실패 시 샘플 데이터 표시
VITE_DEBUG=false                              # 성능 로그 출력
```

### 3.2 환경변수 읽기 모듈 (고정)

```javascript
// src/config/env.js — 이 파일 그대로 사용, 변수명 변경 금지

export const env = Object.freeze({
  apiBaseUrl:       import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001',
  lmStudioUrl:      import.meta.env.VITE_LM_STUDIO_URL || 'http://localhost:1234/v1',
  openaiApiKey:     import.meta.env.VITE_OPENAI_API_KEY || '',
  anthropicApiKey:  import.meta.env.VITE_ANTHROPIC_API_KEY || '',
  bizInfoUrl:       import.meta.env.VITE_BIZINFO_API_URL || '',
  msitUrl:          import.meta.env.VITE_MSIT_API_URL || '',
  mssUrl:           import.meta.env.VITE_MSS_API_URL || '',
  kstartupUrl:      import.meta.env.VITE_KSTARTUP_API_URL || '',
  bizKey:           import.meta.env.VITE_BIZ_KEY || '',
  apiKey:           import.meta.env.VITE_API_KEY || '',
  noticeSearchNm:   import.meta.env.VITE_NOTICE_SEARCH_NM || '자동차 부품',
  useMockWhenFailed:import.meta.env.VITE_USE_MOCK_WHEN_FAILED !== 'false',
  debug:            import.meta.env.VITE_DEBUG === 'true',
})
```

---

## 4. 완전한 package.json

```json
{
  "name": "ajin-bizai",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "server": "node server.js",
    "dev:all": "concurrently \"npm run dev\" \"npm run server\"",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "eslint src --ext .js,.jsx"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "lucide-react": "^0.454.0",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.4"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.3",
    "autoprefixer": "^10.4.20",
    "concurrently": "^9.1.0",
    "eslint": "^9.13.0",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.14",
    "vite": "^5.4.2",
    "vitest": "^2.1.4"
  }
}
```

---

## 5. requirements.txt (버전 고정)

```
# backend/requirements.txt
fastapi==0.115.4
uvicorn[standard]==0.32.0
pdfplumber==0.11.4
python-docx==1.1.2
pandas==2.2.3
openpyxl==3.1.5
python-multipart==0.0.12
python-dotenv==1.0.1
httpx==0.27.2
sentence-transformers==3.3.1
torch==2.5.1
scikit-learn==1.5.2
```

---

## 6. 디렉토리 구조 (목표 상태 완전 버전)

```
AJIN_PROJECT/
│
├── web-react/                              # React 프론트엔드
│   ├── .env.example                        # 환경변수 템플릿
│   ├── .env                                # 실제 환경변수 (gitignore)
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── server.js                           # Express 프록시 서버 (포트 3001)
│   └── src/
│       ├── main.jsx
│       ├── App.jsx                         ← 라우팅 (PRD-03 참조)
│       ├── App.css
│       ├── index.css
│       │
│       ├── constants/
│       │   ├── pages.js                    ← PAGE 상수 (PRD-03 참조)
│       │   └── storageKeys.js              ← STORAGE_KEYS (PRD-03 참조)
│       │
│       ├── config/
│       │   ├── env.js                      ← 환경변수 (위 참조)
│       │   └── defaults.js                 ← 기본값 설정
│       │
│       ├── types/
│       │   └── index.ts                    ← 타입 정의 (PRD-04 참조)
│       │
│       ├── contexts/
│       │   └── AppContext.jsx              ← 전역 상태 (PRD-07 참조)
│       │
│       ├── hooks/
│       │   ├── useAppState.js              ← 상태 훅
│       │   ├── useNotices.js               ← 공고 로딩 훅 (기존)
│       │   └── useAutoSave.js              ← 자동저장 훅 (신규)
│       │
│       ├── services/
│       │   ├── storage.js                  ← localStorage 서비스
│       │   └── notificationService.js      ← 알림 체크
│       │
│       ├── api/
│       │   ├── noticesApi.js               ← 공고 수집 (PRD-04 F-01)
│       │   ├── lmStudioApi.js              ← LLM 호출 (PRD-04 F-06)
│       │   └── fileProcessApi.js           ← 파일 파싱 API 호출 (신규)
│       │
│       ├── components/
│       │   └── ui/                         ← shadcn/ui (기존 유지)
│       │       ├── alert.jsx
│       │       ├── badge.jsx
│       │       ├── button.jsx
│       │       ├── card.jsx
│       │       ├── input.jsx
│       │       ├── label.jsx
│       │       ├── separator.jsx
│       │       └── textarea.jsx
│       │
│       ├── features/
│       │   ├── layout/
│       │   │   └── TopNav.jsx              ← 네비게이션 (기존 개선)
│       │   │
│       │   ├── dashboard/
│       │   │   └── DashboardPage.jsx       ← 신규
│       │   │
│       │   ├── notices/
│       │   │   ├── components/
│       │   │   │   ├── NoticeCard.jsx      ← 기존 개선
│       │   │   │   ├── NoticeFilters.jsx   ← 기존 유지
│       │   │   │   ├── NoticeList.jsx      ← 기존 유지
│       │   │   │   └── NoticeDetail.jsx    ← 기존 개선
│       │   │   ├── hooks/
│       │   │   │   └── useNotices.js       ← 기존 유지
│       │   │   └── utils/
│       │   │       ├── date.js             ← 기존 유지
│       │   │       ├── filtering.js        ← 기존 개선
│       │   │       ├── match.js            ← 기존 개선
│       │   │       ├── normalize.js        ← 기존 개선
│       │   │       └── evaluationParser.js ← 신규
│       │   │
│       │   ├── apply/                      ← 신규 (신청 준비)
│       │   │   ├── ApplyPrepPage.jsx
│       │   │   ├── StepUpload.jsx
│       │   │   ├── StepAnalysis.jsx
│       │   │   ├── StepDiagnosis.jsx
│       │   │   ├── StepInterview.jsx
│       │   │   ├── StepReadiness.jsx
│       │   │   └── interviewQuestions.js
│       │   │
│       │   ├── draft/
│       │   │   ├── ChatDraftPage.jsx       ← 기존 개선
│       │   │   └── QuickDraftPage.jsx      ← 기존 이름 변경 (DraftPage)
│       │   │
│       │   ├── simulation/                 ← 신규
│       │   │   └── SimulationPage.jsx
│       │   │
│       │   ├── history/                    ← 신규
│       │   │   └── HistoryPage.jsx
│       │   │
│       │   ├── bookmarks/                  ← 신규
│       │   │   └── BookmarksPage.jsx
│       │   │
│       │   └── pages/                      ← 기존 (알림, 설정)
│       │       ├── NotificationPage.jsx
│       │       └── SettingsPage.jsx
│       │
│       └── lib/
│           └── utils.js                    ← cn() 유틸 (기존)
│
├── backend/                                ← 신규 Python 백엔드
│   ├── main.py                             ← FastAPI 앱 진입점
│   ├── .env                                ← 백엔드 환경변수
│   ├── requirements.txt
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── files.py                        ← 파일 파싱 API
│   │   ├── diagnosis.py                    ← AI 진단 API
│   │   └── llm.py                          ← LLM 프록시 (선택)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── file_parser.py                  ← PDF/DOCX 파싱
│   │   ├── diagnosis.py                    ← 부족정보 진단
│   │   └── similarity.py                   ← Sentence Transformer
│   └── models/
│       ├── __init__.py
│       └── schemas.py                      ← Pydantic 모델
│
├── docker-compose.yml
└── README.md
```

---

## 7. backend/main.py (완전한 코드)

```python
# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import files, diagnosis

app = FastAPI(
    title="AJIN BizAI Backend",
    version="1.0.0",
    docs_url="/api/docs",
)

# CORS 설정 — 프론트엔드 주소만 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3001",   # Express proxy
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(files.router)
app.include_router(diagnosis.router)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}
```

---

## 8. Express 프록시 서버

```javascript
// web-react/server.js
import express from 'express'
import { createProxyMiddleware } from 'http-proxy-middleware'
import cors from 'cors'
import 'dotenv/config'

const app = express()
const PORT = process.env.PORT || 3001

app.use(cors({ origin: 'http://localhost:5173', credentials: true }))
app.use(express.json())

// 공공 API 프록시 (API 키를 서버에서 주입)
app.use('/proxy/bizinfo', createProxyMiddleware({
  target: process.env.BIZINFO_API_URL || 'https://www.bizinfo.go.kr',
  changeOrigin: true,
  pathRewrite: { '^/proxy/bizinfo': '' },
  on: {
    proxyReq: (proxyReq) => {
      // API 키 헤더 추가
      if (process.env.BIZ_KEY) {
        const url = new URL(proxyReq.path, 'http://dummy')
        url.searchParams.set('serviceKey', process.env.BIZ_KEY)
        proxyReq.path = url.pathname + url.search
      }
    },
  },
}))

// Python 백엔드 프록시
app.use('/api', createProxyMiddleware({
  target: 'http://localhost:8000',
  changeOrigin: true,
}))

app.listen(PORT, () => console.log(`AJIN BizAI proxy server running on port ${PORT}`))
```

---

## 9. Docker Compose

```yaml
# docker-compose.yml
version: '3.9'

services:
  frontend:
    build:
      context: ./web-react
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    environment:
      - VITE_API_BASE_URL=http://proxy:3001
    depends_on:
      - proxy

  proxy:
    build:
      context: ./web-react
      dockerfile: Dockerfile.proxy
    ports:
      - "3001:3001"
    env_file:
      - ./web-react/.env
    depends_on:
      - backend

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - ./backend/.env
    volumes:
      - ./backend:/app

volumes: {}
```

---

## 10. vite.config.js

```javascript
// web-react/vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/proxy': {
        target: 'http://localhost:3001',
        changeOrigin: true,
      },
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          ui: ['lucide-react'],
        },
      },
    },
  },
})
```
