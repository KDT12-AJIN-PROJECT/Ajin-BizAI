# AJIN BizAI

> **정부지원사업 신청서 자동화 SaaS**
> 공고 검색 → 분석 → 사업계획서 초안 작성 → 평가 → export 까지 한 흐름으로 처리합니다.
> 본 문서는 새 팀원이 코드를 받고 5분 안에 띄울 수 있고, 1시간 안에 전체 구조를 이해할 수 있도록 작성된 **포괄 가이드** 입니다.

---

## 목차

- [1. 프로젝트 소개](#1-프로젝트-소개)
- [2. 빠른 시작 (Quick Start)](#2-빠른-시작-quick-start)
- [3. 시스템 아키텍처](#3-시스템-아키텍처)
- [4. 폴더 구조 전체](#4-폴더-구조-전체)
- [5. 백엔드 상세 가이드](#5-백엔드-상세-가이드)
- [6. 프론트엔드 상세 가이드](#6-프론트엔드-상세-가이드)
- [7. 초안 작성 흐름 (Step 1~5)](#7-초안-작성-흐름-step-1-5)
- [8. 자료실 + AI 본문 분석](#8-자료실--ai-본문-분석)
- [9. 환경변수 레퍼런스](#9-환경변수-레퍼런스)
- [10. DB 스키마 + 마이그레이션](#10-db-스키마--마이그레이션)
- [11. 외부 API + LLM 통합](#11-외부-api--llm-통합)
- [12. 테스트 + 검증](#12-테스트--검증)
- [13. 개발 컨벤션 + 워크플로](#13-개발-컨벤션--워크플로)
- [14. 트러블슈팅](#14-트러블슈팅)
- [15. 자주 묻는 질문 (FAQ)](#15-자주-묻는-질문-faq)
- [16. 참고 자료](#16-참고-자료)

---

## 1. 프로젝트 소개

### 1.1 무엇을 만드는가

정부 산하 기관들이 매년 발표하는 정부지원사업(R&D, 스마트공장 등) 공고문은 분량이 많고 형식이 제각각입니다. 한 기업이 적합한 공고를 찾고 사업계획서를 작성하려면 수십 시간이 들어갑니다.

**AJIN BizAI**는 이 과정을 다음과 같이 자동화합니다.

1. **공고 검색** — 공공데이터 API 4종(기업마당 / 과기부 / 중기부 / K-Startup)을 수집해 한 화면에 보여줍니다. 키워드/지역/기업규모/적합도 임계값 등으로 필터링하고 마감일 임박순 정렬을 지원합니다.
2. **공고 상세 + AI 분석** — 첨부파일(HWP/PDF)을 backend가 다운로드 → 텍스트 추출 → LLM(LM Studio gemma-4-e4b 또는 OpenAI gpt-4o)에 던져 "지원 대상 / 지원 내용 / 제출 서류 / 신청 기간 / 마감일 / 지역 / 제한 사항 / 사업 개요 / 문의처" 10개 항목으로 자동 분류합니다.
3. **제출 양식 분석** — 사용자가 업로드한 사업계획서 양식 PDF를 layout-aware 추출 → form_parser LLM이 섹션/문항/표 구조를 JSON 스키마로 변환합니다. 표는 cell 단위(header_cells + data_rows)까지 보존됩니다.
4. **참고자료 매핑** — 사용자가 올린 참고자료(회사 자료, 첨부, 필요 자료)에서 evidence를 추출하고, 양식의 각 문항과 매핑합니다(BM25 + 임베딩).
5. **초안 작성** — Step3에서 문항별로 draft_writer LLM이 evidence 기반 초안을 생성합니다. 사용자는 inline 편집 가능.
6. **평가** — Step4에서 draft_evaluator LLM이 평가기준 매핑 + 점수 + 보완 제안을 출력합니다.
7. **Export** — Step5에서 DOCX / HWPX / TXT 로 다운로드.

### 1.2 누가 쓰는가

- **1차 사용자**: 중소·중견 제조기업 사업개발 담당자
- **2차 사용자**: 정부지원사업 컨설팅 회사
- **현재 단계**: MVP 개발 중 (v0.2 Phase). 단일 사용자(`anonymous`)로 동작하며 인증·결제 없음.

### 1.3 주요 기술 스택

| 영역 | 기술 |
|------|------|
| Frontend | React 18 + Vite 8 + Tailwind 3 + shadcn/ui + lucide-react + react-router 7 |
| Backend | FastAPI + SQLAlchemy 2 + Pydantic 2 + httpx + Python 3.13 |
| DB | SQLite (v0.2), pgvector 검토 (v0.3) |
| LLM | OpenAI gpt-4o / gpt-4o-mini, Anthropic Claude Haiku/Sonnet/Opus, LM Studio (local gemma-4-e4b / qwen2.5-7b) |
| 파일 파싱 | pdfplumber + pypdfium2 + python-docx + olefile (HWP) |
| Vector | chromadb + rank-bm25 |
| 테스트 | pytest + pytest-asyncio + Playwright (e2e) + vitest |
| 배포 | Express (server.js, port 8080) — production, Vite dev server (5173) — 개발 |

### 1.4 핵심 정책 한 줄 요약

- **단일 사용자(anonymous)** — auth 미구현, company_profile_id = `"anonymous"` 고정
- **No-LLM 게이트** — Step5 export는 LLM 호출 X (test_03 §3.11.5)
- **MOCK 자동 폴백 금지** — 실제 backend 응답이 비면 빈 결과 + 명확한 에러 메시지
- **/lab v0.1 폐기** — 2026-05-09. Streamlit 기반 prototype 제거. snapshot은 `local/prompt/v0.2/LAB_v0.1_snapshot.md`

### 1.5 현재 진행 단계 (2026-05-25 기준)

- ✅ Phase 4-G frontend 통합 5 step (DraftPageV2)
- ✅ Phase 4-H A1/A2-lite/A3-lite/B1-β/B2-lite 테스트 인프라
- ✅ NOAPI P1+P2+P3 — LLM 호출 안전망 + OpenAI 실연결
- ✅ FormParser v2 P1 — Layout IR + Semantic Markdown
- ✅ form_prd 1~6 — FormSchema persistence + edit UI v0.1
- ✅ 2026-05-19 Option C — table cell grid (header_cells/data_rows)
- ✅ 2026-05-25 자료실 신규 + HWP 추출/생성 + DetailPage AI 본문 분석 + Step3 진입 오류 수정 (B+A2)
- 🚧 다음: Phase 5 H1~H4 (Hybrid routing) → v0.3 RAG → Phase 7 베타

---

## 2. 빠른 시작 (Quick Start)

### 2.1 사전 준비 (1회)

#### 필수 도구

| 도구 | 권장 버전 | 확인 명령 |
|------|----------|----------|
| Python | **3.13** (system Python) | `python --version` |
| Node.js | 18 이상 | `node --version` |
| npm | 9 이상 (Node와 함께 설치됨) | `npm --version` |
| Git | 2.40 이상 | `git --version` |

> **⚠ Conda 환경 금지**
> Conda `llm_api` / `bizai` 환경은 SQLAlchemy 미설치 → import 에러. 반드시 **system Python 3.13** 사용.
> Windows 경로: `C:\Users\<USER>\AppData\Local\Programs\Python\Python313\python.exe`

#### 저장소 받기

```bash
git clone https://github.com/studentjung99/AJIN_PROJECT.git
cd AJIN_PROJECT
```

### 2.2 환경변수 설정 (1회)

#### Backend `.env`

```powershell
copy backend\.env.example backend\.env
```

`backend/.env` 최소 항목:

```ini
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...                      # OpenAI 키 (https://platform.openai.com/api-keys)
OPENAI_MODEL_ANALYSIS=gpt-4o-mini
OPENAI_MODEL_FORM_PARSER=gpt-4o            # 큰 폼에선 TPM 한도 주의
OPENAI_MODEL_DRAFT=gpt-4o-mini

# LM Studio (DetailPage AI 본문 분석용 — 선택)
LM_STUDIO_URL=http://127.0.0.1:1234
LM_STUDIO_MODEL=google/gemma-4-e4b
LM_STUDIO_TOKEN=sk-lm-<your_token>

# 개발 환경
APP_ENV=development
```

> **OPENAI_API_KEY 없으면?** — 백엔드는 startup은 되지만 `/api/analysis/parse-form`, `/api/analysis/extract-evidence` 등 LLM 호출이 실패합니다. `AI_PROVIDER=mock` 으로 두면 mock 응답 fallback.

#### Frontend `.env`

```powershell
copy web-react\.env.example web-react\.env
```

`web-react/.env`는 기본값 그대로 두면 됩니다. 주요 항목:

```ini
VITE_API_BASE_URL=http://localhost:8000
VITE_ENABLE_ANALYSIS_DEV_MODE=true        # /draft-v2 활성화
VITE_API_KEY=YOUR_API_KEY                  # 공공데이터 포털 키 (선택)
VITE_BIZ_KEY=YOUR_BIZ_KEY                  # 기업마당 키 (선택)
```

#### Frontend `.env.server` (Production / LM Studio Token 사용 시)

```powershell
copy web-react\.env.example web-react\.env.server
```

Vite proxy(`/proxy/lmstudio`)가 자동으로 `Authorization: Bearer ${LM_STUDIO_TOKEN}` 헤더를 주입합니다.

```ini
LM_STUDIO_URL=http://127.0.0.1:1234
LM_STUDIO_TOKEN=sk-lm-<your_token>
API_KEY=<공공데이터_api_key>
BIZ_KEY=<기업마당_key>
```

### 2.3 Backend 실행

새 터미널 창에서:

```powershell
cd backend
python -m uvicorn main:app --port 8000 --host 127.0.0.1 --log-level info
```

> **⚠ `--reload` 옵션 사용 금지** (Windows). watchfiles 충돌로 서버가 hang/crash 합니다. 코드 수정 시 `Ctrl+C` 후 재실행하세요.

정상 기동 확인:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

브라우저: `http://localhost:8000/api/health` → `{"status": "ok"}` 보이면 OK.

### 2.4 Frontend 실행

또 다른 새 터미널 창에서:

```powershell
cd web-react
npm install          # 처음 1회 또는 package.json 변경 시
npm run dev
```

기동 후:
```
  ➜  Local:   http://localhost:5173/
```

브라우저: `http://localhost:5173` 진입 → 대시보드 표시.

### 2.5 첫 사용 흐름 (5분 데모)

1. **대시보드** → 상단 **`신규 작성`** 클릭
2. **Step1 자료 업로드** → 공고문 PDF + 양식 PDF + 참고자료 업로드
3. **Step2 분석** → 자동 진행. 끝나면 `Step 2 분석 결과 확정 →` 클릭
4. **Step3 초안 작성** → 문항별로 AI가 초안 생성. 사용자 inline 편집
5. **Step4 평가** → AI 평가 + 보완 제안
6. **Step5 Export** → DOCX / HWPX / TXT 다운로드

### 2.6 서버 중지

```powershell
# 각 터미널에서
Ctrl+C
```

좀비 프로세스 정리:
```powershell
netstat -ano | findstr LISTENING | findstr "8000 5173"
Stop-Process -Id <PID> -Force
```

---

## 3. 시스템 아키텍처

### 3.1 컴포넌트 다이어그램

```
┌────────────────────────────────────────────────────────────────────┐
│  사용자 (브라우저)                                                  │
│  http://localhost:5173                                              │
└─────────┬───────────────────────────────────────────────────────────┘
          │ HTTP / WebSocket (HMR)
          ▼
┌────────────────────────────────────────────────────────────────────┐
│  Vite Dev Server (web-react, port 5173)                            │
│  - React 18 + Vite 8                                                │
│  - Proxy: /api → :8000 (FastAPI)                                    │
│           /proxy/bizinfo → bizinfo.go.kr                            │
│           /proxy/apis    → apis.data.go.kr                          │
│           /proxy/lmstudio → 127.0.0.1:1234 (+Bearer 토큰 주입)      │
└─────────┬───────────────────────────────────────────────────────────┘
          │ /api/**
          ▼
┌────────────────────────────────────────────────────────────────────┐
│  FastAPI Backend (port 8000)                                       │
│  routers/                                                           │
│    analysis.py   — v0.2 분석 파이프라인 (parse-notice/-form, ...)   │
│    notices.py    — 공고 검색 + AI 본문 분석                          │
│    files.py      — 파일 업로드/파싱/prefetch/export-hwpx             │
│    library.py    — 자료실 통합 API (회사/첨부/필요)                  │
│    company.py    — CompanyFile (A3) — 기업 자료                      │
│    drafts.py     — V1 legacy drafts                                  │
│    chat.py       — Step3 보완 대화                                   │
│    diagnosis.py / ai.py / bookmarks.py / profile.py                  │
│                                                                     │
│  services/                                                          │
│    ai_provider.py — Provider 추상 (Mock/Anthropic/OpenAI)            │
│    openai_provider.py / anthropic_provider.py / mock_provider.py     │
│    lm_studio_client.py — LM Studio httpx 클라이언트 (reasoning 대응) │
│    form_layout_builder.py / form_llm_input_builder.py                │
│    form_parser_hybrid.py / form_parser_postprocessor.py              │
│    table_normalizer.py / table_promoter.py / table_keywords.py       │
│    evidence_chunker.py / evidence_embedder.py / evidence_store.py    │
│    mapping_pipeline.py / evidence_matcher.py / item_query_builder.py │
│    llm_response_parser.py / llm_token_budget.py                      │
└─────────┬─────────────────────────────────┬─────────────────────────┘
          │                                  │
          ▼                                  ▼
┌─────────────────────┐         ┌──────────────────────────────┐
│  SQLite             │         │  외부 LLM API                │
│  backend/ajin.db    │         │  - OpenAI (gpt-4o/-mini)     │
│  + chroma_data/     │         │  - Anthropic (Claude)        │
│                     │         │  - LM Studio (로컬, gemma)   │
└─────────────────────┘         └──────────────────────────────┘
          │
          ▼
┌─────────────────────┐         ┌──────────────────────────────┐
│  Disk Storage        │         │  외부 공공데이터 API         │
│  backend/data/       │         │  - 기업마당 (bizinfo)        │
│    uploads/company/  │         │  - 과기부 (msit)             │
│    sessions/         │         │  - 중기부 (mss)              │
│                      │         │  - K-Startup                 │
└──────────────────────┘         └──────────────────────────────┘
```

### 3.2 데이터 흐름 (한 세션 기준)

```
1. 사용자가 Step1에서 공고문/양식/참고자료 업로드
   └─ POST /api/analysis/files (multipart)
      └─ files.py parse_upload_bytes() — PDF/DOCX/HWP/XLSX 텍스트 추출
         └─ ApplicationSession 생성 + JSON-piggyback (notice_schema_json.attachments)

2. Step2 진입 → 자동 분석 트리거
   ├─ POST /api/analysis/parse-notice
   │   └─ notice_analyst LLM → NoticeSchema
   │
   ├─ POST /api/analysis/parse-form
   │   └─ form_layout_builder → Layout IR (pages/blocks/tables)
   │   └─ form_llm_input_builder → Semantic Markdown
   │   └─ form_parser LLM (hybrid: regex chapter + chunked parallel)
   │   └─ table_normalizer + table_promoter → FormSchema + cell grid
   │
   ├─ POST /api/analysis/extract-evidence
   │   └─ evidence_chunker → 참고자료 split
   │   └─ evidence_embedder → ChromaDB 벡터 저장
   │
   ├─ POST /api/analysis/analyze-company
   │   └─ company_analyzer LLM → CompanySchema (강점/약점/역량)
   │
   └─ POST /api/analysis/mapping (BackgroundTasks)
       └─ mapping_pipeline (BM25 + 임베딩) → MappingResult per question

3. Step3 진입 → 문항별 초안
   └─ POST /api/analysis/write-draft-item (per question)
      └─ draft_writer LLM (used_evidence_ids 환각 안전망)
         └─ DraftItem (content / table_data / used_evidence_ids / status)

4. Step4 평가
   └─ POST /api/analysis/evaluate-draft
      └─ draft_evaluator LLM → 평가 점수 + 보완 제안

5. Step5 Export
   └─ POST /api/analysis/export-docx (mock — Phase 4-G 후반 실구현 예정)
   └─ POST /api/files/export-hwpx (실구현)
```

### 3.3 핵심 ontology (PRD §13.1)

```
ApplicationSession (1) ─┬─ (N) EvidenceItem
                        ├─ (N) MappingResult
                        ├─ (N) MissingMaterial
                        ├─ (N) SupplementalMaterial
                        ├─ (1) FitAnalysis
                        ├─ (N) EvalCriteriaMapping
                        └─ (N) DraftItem

CompanyFile (N) ──── soft ref ──── ApplicationSession.selected_company_file_ids[]
```

자세한 스키마는 [§10](#10-db-스키마--마이그레이션) 참조.

---

## 4. 폴더 구조 전체

### 4.1 루트

```
AJIN_PROJECT/
├─ README.md                          ← 이 파일
├─ LICENSE                            ← MIT
├─ CLAUDE.md                          ← Claude Code 운영 지침 (commit, 팀 공유)
├─ CLAUDE.local.md                    ← 개인 블로그/워크로그 규칙 (gitignore)
├─ .gitignore                         ← 환경/캐시/log/대용량 파일 차단
├─ .github/                           ← GitHub Actions yml
├─ .devcontainer/                     ← VS Code Dev Container 설정
├─ .blog/worklog/{YYYY-MM-DD}.md      ← 일자별 작업 기록 (gitignore)
│
├─ PRD/                               ← 공식 PRD (committed, 본문 불변)
│  ├─ PRD-01_overview.md
│  ├─ PRD-02_user.md
│  ├─ ...
│  ├─ PRD-12_constraints.md
│  └─ PRD-13_change_log.md            ← 변경 이력 누적 (수정 가능한 유일한 PRD)
│
├─ backend/                           ← FastAPI 서버 (§5 참조)
├─ web-react/                         ← React + Vite 프론트엔드 (§6 참조)
│
├─ local/                             ← 개인 작업장 (gitignore)
│  ├─ 1_PRD/                          ← v0.2 / v3.1 / v3.2 / form_prd / features
│  ├─ 2_work/                         ← STATUS.md / TODO_polish.md / reports/ / plans/ / db/
│  ├─ 3_design/                       ← HTML 목업
│  ├─ 4_images/                       ← chatgpt / refs / screenshots
│  ├─ 5_samples/                      ← 테스트용 공고 + 양식 (대용량)
│  ├─ 6_archive/                      ← 폐기된 작업물
│  └─ prompt/                         ← Master/strategy 보존
│
├─ docs/                              ← 운영 보조 문서
├─ config/                            ← pricing.json 등 운영 config
├─ scripts/                           ← 운영 스크립트
└─ test-results/                      ← Playwright e2e 산출물 (gitignore)
```

### 4.2 backend/

```
backend/
├─ main.py                            ← FastAPI 앱 진입점, CORS, router 등록
├─ database.py                        ← SQLAlchemy engine + SessionLocal
├─ models.py                          ← SQLAlchemy ORM 모델 (Notice/Draft/Bookmark/Profile/ApplicationSession/...)
├─ schemas.py                         ← 일부 Pydantic 스키마 (notice/draft/bookmark)
├─ requirements.txt                   ← Python 의존성
├─ pytest.ini                         ← pytest 설정
├─ ajin.db                            ← SQLite DB (gitignore)
├─ .env / .env.example                ← 환경변수 (실제 값 gitignore)
│
├─ routers/                           ← FastAPI APIRouter 12개
│  ├─ __init__.py
│  ├─ analysis.py                     ← ★ v0.2 분석 파이프라인 (가장 큰 라우터, 4000+ 줄)
│  ├─ notices.py                      ← 공고 검색 + AI 본문 분석 (/api/notices/*)
│  ├─ files.py                        ← 파일 업로드/파싱 + prefetch-url + export-hwpx
│  ├─ library.py                      ← 자료실 통합 API (/api/library/*) — 2026-05-25 신규
│  ├─ company.py                      ← CompanyFile (A3) — 기업 자료
│  ├─ drafts.py                       ← V1 legacy drafts
│  ├─ chat.py                         ← Step3 보완 대화 (/api/chat/draft-assist)
│  ├─ diagnosis.py                    ← 진단 결과
│  ├─ ai.py                           ← V1 AI 호출 wrapper
│  ├─ bookmarks.py                    ← 북마크
│  ├─ profile.py                      ← V1 기업 프로필
│
├─ services/                          ← 비즈니스 로직 25+개
│  ├─ ai_provider.py                  ← Provider 추상 base
│  ├─ openai_provider.py              ← OpenAI 구현 (form_parser, draft_writer, ...)
│  ├─ anthropic_provider.py           ← Anthropic 구현 (Claude Haiku/Sonnet/Opus)
│  ├─ mock_provider.py                ← Mock 응답
│  ├─ local_provider.py               ← Local LLM (LM Studio) 구현
│  ├─ lm_studio_client.py             ← LM Studio httpx 클라이언트 (gemma reasoning 대응)
│  ├─ ai_cost.py                      ← 비용 계산 (token → KRW)
│  │
│  ├─ form_layout_builder.py          ← PDF → Layout IR (pdfplumber + pypdfium2)
│  ├─ form_llm_input_builder.py       ← Layout IR → Semantic Markdown
│  ├─ form_parser_hybrid.py           ← Hybrid form_parser (chunked parallel)
│  ├─ form_parser_postprocessor.py    ← parser hint 주입 (header/table 후보)
│  ├─ table_normalizer.py             ← Layout 표 정규화 (header_path 계산)
│  ├─ table_promoter.py               ← LLM 누락 표 자동 승격 + cell grid
│  ├─ table_keywords.py               ← 표 컬럼 키워드 사전
│  │
│  ├─ evidence_chunker.py             ← 참고자료 split
│  ├─ evidence_embedder.py            ← ChromaDB 임베딩
│  ├─ evidence_store.py               ← Vector store CRUD
│  ├─ evidence_matcher.py             ← BM25 + 임베딩 매칭
│  ├─ item_query_builder.py           ← 문항별 검색 쿼리 생성
│  ├─ mapping_pipeline.py             ← 매핑 파이프라인 (백그라운드 태스크)
│  │
│  ├─ company_context_resolver.py     ← 기업 정보 → 평가기준 매핑 컨텍스트
│  ├─ rubric_resolver.py              ← 평가 rubric 정규화
│  │
│  ├─ llm_response_parser.py          ← JSON 펜스 제거 + 환각 안전망
│  ├─ llm_token_budget.py             ← context overflow 방지
│  ├─ audit_logger.py                 ← AI 호출 로그 기록
│  └─ diagnosis.py                    ← 완성도 계산
│
├─ ontology/                          ← Pydantic v0.2 스키마
│  ├─ __init__.py
│  └─ schemas.py                      ← FormSchema / NoticeSchema / DraftItem / EvidenceSchema 등 11종
│
├─ migrations/                        ← 수동 마이그레이션 (Alembic 대신 idempotent SQL)
│  ├─ 0001_draft_version.py
│  ├─ 0002_audit_log.py
│  ├─ 0003_v02_schema.py
│  ├─ 0004_company_file_parsed_text.py
│  └─ 0005_eval_criteria_history.py
│
├─ prompts/                           ← LLM 시스템 프롬프트 (Markdown)
│  ├─ form_parser.md                  ← 제출양식 분석 (v1.4)
│  ├─ notice_analyst.md               ← 공고 분석
│  ├─ company_analyzer.md             ← 기업 분석
│  ├─ draft_writer.md                 ← 초안 작성
│  ├─ draft_evaluator.md              ← 평가
│  ├─ missing_material.md             ← 부족자료 추출
│  ├─ draft_rewriter.md               ← 초안 재작성
│  └─ eval_criteria_mapper.md         ← 평가기준 매핑
│
├─ hwpx/                              ← HWP/HWPX 파일 모듈 — 2026-05-25 통합
│  ├─ __init__.py
│  ├─ hwp_reader.py                   ← HWP → text (read_hwp / read_hwp_bytes)
│  ├─ hwpx_writer.py                  ← text → HWPX (save_hwpx / save_hwpx_bytes)
│  └─ this_is_hwpx.hwpx               ← HWPX 템플릿 (writer가 사용)
│
├─ tests/                             ← pytest
│  ├─ test_smoke.py                   ← smoke 14 tests
│  ├─ test_b1_confirm_step2.py        ← Step2 confirm
│  ├─ test_b2_step3_ready.py
│  ├─ test_b3_draft_items_initialize.py
│  ├─ test_c1_reference_storage.py
│  ├─ test_c1_5_announcement_signals.py
│  ├─ test_c1_6_rubric_resolver.py
│  ├─ test_c2_gate.py
│  ├─ test_c3_mapping_pipeline.py
│  ├─ test_c5a_smoke.py / _c5b / _c5c
│  ├─ test_a3_*.py                    ← Layout audit
│  ├─ test_openai_notice_analyst.py
│  └─ fixtures/llm_responses/         ← 8 LLM 응답 fixture
│
├─ data/                              ← 런타임 데이터 (gitignore)
│  ├─ sessions/{session_id}/debug/    ← FORM_PARSER_DEBUG=true 시 산출물
│  └─ uploads/company/{profile_id}/   ← CompanyFile 디스크 BLOB
│
├─ backups/                           ← DB 백업 (gitignore)
└─ chroma_data/                       ← ChromaDB persistent (gitignore)
```

### 4.3 web-react/

```
web-react/
├─ package.json                       ← npm scripts: dev / build / lint / e2e
├─ vite.config.js                     ← Vite + proxy 설정 (/api, /proxy/lmstudio 등)
├─ playwright.config.js               ← e2e 설정
├─ eslint.config.js / postcss.config.js / tailwind.config.js
├─ Dockerfile / docker-compose.yml    ← 컨테이너 빌드 (선택)
├─ server.js                          ← Express production 서버 (port 8080)
├─ .env / .env.example / .env.server  ← 환경변수
├─ index.html                         ← Vite entry HTML
│
├─ src/
│  ├─ main.jsx                        ← React entry
│  ├─ App.jsx                         ← ★ 라우팅 + 전역 state (1000+ 줄)
│  ├─ App.css / index.css             ← 전역 스타일
│  │
│  ├─ api/                            ← Backend / 외부 API 클라이언트
│  │  ├─ backendApi.js                ← /api/* 통합 (analysisApi / libraryApi / companyApi / chatApi 등)
│  │  ├─ noticesApi.js                ← /api/notices/search + 정규화 + 마감 drop
│  │  └─ lmStudioApi.js               ← LM Studio 직접 호출 (3줄 요약, 초안 등)
│  │
│  ├─ config/
│  │  ├─ env.js                       ← import.meta.env 래퍼 (apiKey/bizKey/lmStudioUrl 등)
│  │  ├─ defaults.js                  ← 기본 프로필 / 필터 옵션
│  │  └─ demoData.js                  ← (deprecated) DEMO_NOTICES / DEMO_DRAFTS — 더 이상 사용 X
│  │
│  ├─ features/                       ← 도메인별 분리
│  │  ├─ layout/                      ← 공통 레이아웃
│  │  │  ├─ Sidebar.jsx               ← 좌측 사이드바 (기업 프로필 + 작성 중인 공고)
│  │  │  └─ TopNav.jsx                ← 상단 메뉴 (대시보드/공고검색/신규작성/초안이어작성/자료실/...)
│  │  │
│  │  ├─ notices/
│  │  │  ├─ hooks/useNotices.js       ← 공고 로딩 hook
│  │  │  ├─ components/FileViewer.jsx ← PDF/HWP/이미지 미리보기 + 본문 추출
│  │  │  └─ utils/                    ← normalize / filtering / date / match
│  │  │
│  │  ├─ pages/                       ← 라우트별 페이지
│  │  │  ├─ DashboardPage.jsx
│  │  │  ├─ SearchPage.jsx            ← 공고 검색 (필터/정렬/탭/페이지네이션)
│  │  │  ├─ DetailPage.jsx            ← ★ 공고 상세 + AI 본문 분석 카드
│  │  │  ├─ DraftPage.jsx             ← V1 legacy 초안 작성 (TXT/HWPX/DOCX 다운로드)
│  │  │  ├─ MaterialsLibraryPage.jsx  ← 자료실 (2026-05-25 신규)
│  │  │  ├─ BookmarkPage.jsx
│  │  │  ├─ DraftListPage.jsx         ← 작성 중 초안 리스트
│  │  │  ├─ SettingsPage.jsx          ← 기업 설정 + 회사 자료 업로드 + 기업 분석
│  │  │  ├─ NotificationPage.jsx
│  │  │  ├─ NotificationSettingsPage.jsx
│  │  │  └─ draft-v2/                 ← ★ V2 5-step 워크플로 (DraftPageV2)
│  │  │     ├─ DraftPageV2.jsx        ← 전체 컨테이너 (sessionStorage / restore)
│  │  │     ├─ Step1Common.jsx        ← (draft-upload/Step1Common.jsx로 이동)
│  │  │     ├─ Step2Analysis.jsx      ← Tab1(공고문) + Tab2(제출양식)
│  │  │     ├─ Step2DevMode.jsx       ← 7 Tab 개발자 모드 (parser_mode/validation/evidence/...)
│  │  │     ├─ Step3Draft.jsx         ← 문항별 초안 작성 (좌 트리 + 우 편집)
│  │  │     ├─ Step4Evaluation.jsx    ← AI 평가
│  │  │     ├─ Step5Export.jsx        ← DOCX/HWPX/TXT export
│  │  │     ├─ components/            ← StepNavigationBar / Step2SummaryPanel 등
│  │  │     └─ shared/
│  │  │        ├─ FormTreePanel.jsx           ← 좌 트리 (섹션/문항 + ✏️/+/🚫)
│  │  │        ├─ FormPreviewPanel.jsx        ← 우 PDF 미리보기 (페이지 네비)
│  │  │        ├─ SupplementalPanel.jsx       ← 선택 문항 세부 + cell grid
│  │  │        ├─ FormQuestionEditor.jsx      ← 문항 편집/추가 모달
│  │  │        ├─ Step2ProgressModal.jsx      ← Step2 진행 상태 모달
│  │  │        ├─ Step4ProceedModal.jsx       ← Step3→4 진입 모달
│  │  │        ├─ AnalysisConfirmModal.jsx    ← Step2→3 확정 모달
│  │  │        └─ EvalCriteriaQuestionPicker.jsx
│  │  │
│  │  ├─ draft-upload/
│  │  │  └─ Step1Common.jsx           ← Step1 자료 업로드 (V1/V2 공용)
│  │  │
│  │  └─ drafts/
│  │     ├─ MyDraftsPage.jsx          ← 내 사업계획서 (제출 이력)
│  │     └─ ArchivePage.jsx           ← 보관함
│  │
│  ├─ components/ui/                  ← shadcn/ui 컴포넌트 (Button/Card/Input/...)
│  ├─ lib/
│  │  ├─ utils.js                     ← cn() (Tailwind class merge)
│  │  ├─ sessionStatus.js             ← ApplicationSession.status enum
│  │  ├─ runtimeLog.js                ← logApi / handleFallback
│  │  ├─ evalCriteriaMappingAdapter.js
│  │  ├─ step2QualityDiagnostic.js
│  │  └─ ...
│  └─ assets/                         ← 이미지 등
│
├─ public/                            ← 정적 자원
├─ e2e/                               ← Playwright 시나리오
├─ tests/                             ← vitest 단위 테스트
├─ dist/                              ← Vite 빌드 산출물 (gitignore)
└─ node_modules/                      ← npm install 결과 (gitignore)
```

### 4.4 local/ (개인 작업장, gitignore)

```
local/
├─ README.md                          ← local 폴더 입구
├─ 1_PRD/
│  ├─ vision/                         ← 비전 문서
│  ├─ v0.2/                           ← ★ 현재 활성 PRD
│  │  ├─ PRD_v0.2_FINAL.md            ← 새 대화 시 첨부 필수
│  │  ├─ test_01_model_strategy.md    ← 모델 라우팅 전략
│  │  ├─ test_03_cost_optimization.md ← 비용 최적화
│  │  └─ ...
│  ├─ v3.1/                           ← v3.1 워크오더
│  ├─ v3.2/                           ← ★ v3.2 워크오더 (현재 진행 중)
│  │  ├─ 00_INDEX.md
│  │  ├─ c-1.5 ~ c-6                  ← Confirmed-step gate / mapping / e2e
│  │  ├─ e-2 ~ e-6                    ← evidence / draft / eval / missing / docx
│  │  └─ m-1, m-2                     ← MyBusinessPlan / Materials Library
│  ├─ form_prd/                       ← 1.md ~ 6.md (FormSchema 작업)
│  └─ features/                       ← 기능별 PRD 작업장
│
├─ 2_work/                            ← ★ 작업 추적 (가장 자주 보는 곳)
│  ├─ STATUS.md                       ← 현재 상태 (항상 최신)
│  ├─ TODO_polish.md                  ← 부채/미해결 누적
│  ├─ update_status_prompt.md         ← STATUS 갱신용 프롬프트
│  ├─ CLAUDE_proposed.md
│  ├─ requirements.txt                ← system Python 환경 snapshot
│  ├─ reports/{날짜}_{기능}_report.md ← 완료 작업 보고서
│  ├─ plans/                          ← 작업 계획 (예: 2026-05-25_ui_refactor_prompt.md)
│  ├─ db/                             ← DB 스키마 dump
│  │  ├─ current_database_ddl.sql
│  │  └─ current_database_erd.mmd
│  └─ work_archive/                   ← 옛 prompt/지시서
│
├─ 3_design/                          ← HTML 목업
├─ 4_images/                          ← chatgpt / refs / screenshots
├─ 5_samples/                         ← 대용량 공고 + 양식 PDF (테스트용)
├─ 6_archive/                         ← 폐기된 작업물 (zip)
└─ prompt/                            ← Master 운영 프롬프트 보존
```

---

## 5. 백엔드 상세 가이드

### 5.1 main.py — 진입점

`backend/main.py` 가 FastAPI 앱을 만들고 모든 라우터를 등록합니다.

```python
app = FastAPI(title="AJIN BizAI Backend", version="1.1.0", docs_url="/api/docs")

# CORS 분기 (APP_ENV=development → localhost only / production → CORS_ALLOWED_ORIGINS)
app.add_middleware(CORSMiddleware, ...)

# router 등록 순서 (의존성 순)
app.include_router(files.router)
app.include_router(diagnosis.router)
app.include_router(notices.router)
app.include_router(drafts.router)
app.include_router(bookmarks.router)
app.include_router(ai.router)
app.include_router(profile.router)
app.include_router(analysis.router)
app.include_router(chat.router)
app.include_router(company.router)
app.include_router(library.router)
```

DB 자동 생성:
```python
Base.metadata.create_all(bind=engine)
```

> **운영 환경**: `APP_ENV=production` + `CORS_ALLOWED_ORIGINS=https://your.domain` 필수.

### 5.2 routers/ 상세

#### 5.2.1 `analysis.py` — ★ v0.2 분석 파이프라인

| Endpoint | 설명 |
|----------|------|
| POST /api/analysis/sessions | 신규 ApplicationSession 생성 |
| GET /api/analysis/sessions | 세션 목록 (status / user_id / notice_id 필터) |
| GET /api/analysis/sessions/{id} | 단일 세션 조회 + form_schema 복원 |
| DELETE /api/analysis/sessions/{id} | soft delete (status='abandoned') — 사이드바 X 버튼 |
| POST /api/analysis/files | multipart 업로드 + parsed_text 영속화 (A1) |
| GET /api/analysis/files | 세션의 첨부 목록 |
| POST /api/analysis/parse-notice | 공고문 → NoticeSchema (notice_analyst LLM) |
| POST /api/analysis/parse-form | 제출양식 → FormSchema (form_parser LLM + hybrid + table_promoter) |
| POST /api/analysis/extract-evidence | 참고자료 → EvidenceItem (chunker + embedder) |
| POST /api/analysis/analyze-company | 기업 자료 → CompanySchema |
| POST /api/analysis/missing-materials | 부족자료 추출 |
| POST /api/analysis/write-draft-item | 단일 문항 초안 작성 (draft_writer LLM) |
| POST /api/analysis/write-all-drafts | 전체 문항 일괄 초안 |
| POST /api/analysis/evaluate-draft | 평가 (draft_evaluator LLM) |
| POST /api/analysis/export-docx | Step5 export (현재 mock URL — Phase 4-G 후반 실구현) |
| PATCH /api/analysis/form-schema/question | 문항 update/add/exclude/move/delete |
| PATCH /api/analysis/form-schema/section | 섹션 update/add |
| POST /api/analysis/confirm-step2 | Step2 분석 결과 확정 (confirmed_schema 영속화) |
| GET /api/analysis/sessions/{id}/step3-ready | Step3 진입 가능 여부 게이트 |
| GET /api/analysis/sessions/{id}/mapping-status | mapping pipeline 진행 상태 |
| POST /api/analysis/mapping | mapping 재실행 (BackgroundTasks) |
| GET /api/analysis/eval-criteria-mappings | 평가기준 매핑 목록 |
| PATCH /api/analysis/eval-criteria-mappings/{id} | 사용자 편집 (history 누적) |
| GET /api/analysis/eval-criteria-mappings/{id}/history |
| POST /api/analysis/reanalyze | 재분석 + drafts_preservation_policy 분기 |

핵심 흐름은 `parse-form` 라우터입니다 (4000+ 줄 중 핵심):

```python
@router.post("/parse-form")
async def parse_form(req, db):
    # 1. form_text 비면 attachments에서 layout-aware 추출
    form_text, layout_meta, layout_pages = _build_layout_aware_text(items)

    # 2. provider.form_parser() 호출 (hybrid or single)
    if req.parser_mode == "hybrid":
        result = await parse_form_hybrid(form_text, ..., provider)
    else:
        result = await provider.form_parser(form_text, ...)

    # 3. table_normalizer + table_promoter (cell grid 포함)
    normalized = normalize_layout_tables(layout_pages)
    result, stats = promote_tables(normalized, result)

    # 4. quality_metrics + repair pass (needs_repair 시 LLM 재호출)
    if quality_metrics["needs_repair"]:
        repair_result = await provider.form_parser(suspect_text, ...)
        result = _merge_repair_schema(result, repair_result)

    # 5. DB 영속화 (form_schema_json.schema + parser_metadata)
    session.form_schema_json["schema"] = result
    return result
```

#### 5.2.2 `notices.py` — 공고 검색 + AI 본문 분석

| Endpoint | 설명 |
|----------|------|
| GET /api/notices/search?q=&refresh= | 4종 공공 API 통합 검색 (DB 캐시 우선) |
| GET /api/notices | 전체 목록 |
| GET /api/notices/{id} | 단일 조회 |
| POST /api/notices/bulk | bulk upsert |
| DELETE /api/notices/{id} | 삭제 |
| POST /api/notices/extract-structured | ★ 본문 텍스트 → LLM 분류 (DetailPage AI 카드) |

`extract-structured` 응답:
```json
{
  "ok": true,
  "data": {
    "title": "스마트공장 구축 지원 사업",
    "target": "자동차 부품 제조 중소기업",
    "benefit": "구축 비용 최대 3억원 지원",
    "documents": "사업계획서, 재무제표, 사업자등록증",
    "period": "2026-06-01 ~ 2026-07-31",
    "deadline": "2026-07-31",
    "region": "전국",
    "limit": "5인 미만 사업장 제외",
    "content": "본 사업은 ...",
    "contact": "1588-1234"
  }
}
```

#### 5.2.3 `files.py` — 파일 업로드/파싱 + prefetch + export

| Endpoint | 설명 |
|----------|------|
| POST /api/parse-file | 단일 파일 업로드 + 텍스트 추출 |
| POST /api/parse-files | 다중 파일 |
| POST /api/files/prefetch-url | ★ 외부 URL → 다운로드 + parse (DetailPage AI/FileViewer) |
| POST /api/files/export-hwpx | ★ text/lines → HWPX 파일 다운로드 (Step5) |

지원 형식: `.pdf`, `.docx`, `.hwp`, `.xlsx`, `.csv`, `.txt`
- PDF: pdfplumber
- DOCX: python-docx
- HWP: olefile + zlib + struct (`backend/hwpx/hwp_reader.py`)
- XLSX/CSV: pandas
- TXT: utf-8-sig

추출 결과:
```json
{
  "filename": "...",
  "ext": ".pdf",
  "size_bytes": 1234567,
  "text": "...(preview ≤10K)",
  "parsed_text": "...(영속 ≤200K)",
  "char_count": 50000,
  "parsed_text_truncated": false,
  "parse_success": true,
  "warning": null
}
```

#### 5.2.4 `library.py` — 자료실 통합 (2026-05-25 신규)

| Endpoint | 설명 |
|----------|------|
| POST /api/library/files | multipart 업로드 + category 지정 + parsed_text 영속 |
| GET /api/library/files?category=&sort= | 리스트 (회사자료/첨부자료/필요자료/전체, recent/name) |
| GET /api/library/files/{id} | 상세 + parsed_text |
| DELETE /api/library/files/{id} | soft delete (status='deleted') |

기존 `company_files` 테이블 재활용. `file_type` 컬럼을 카테고리 enum으로 확장.
- "회사자료" 카테고리는 legacy 5종(회사소개서/재무제표/사업자등록증/특허/기타)까지 포함.

#### 5.2.5 `company.py` — CompanyFile (A3)

기업 프로필 자료 영구 저장. `library.py`보다 먼저 만들어진 라우터. `library.py`가 같은 테이블 재활용.

| Endpoint | 설명 |
|----------|------|
| POST /api/company/files | 업로드 (multipart + 디스크 BLOB) |
| GET /api/company/files | 사용자별 목록 |
| GET /api/company/files/{id} | 단일 조회 (parsed_text 포함) |
| DELETE /api/company/files/{id} | 삭제 (BLOB + DB row) |

Storage: 메타 + parsed_text는 SQLite, 원본 BLOB은 `backend/data/uploads/company/{profile_id}/{file_id}.{ext}`.

#### 5.2.6 `drafts.py` — V1 legacy

V1 흐름의 drafts 테이블 CRUD. V2(`/draft-v2`)에서는 사용 안 함. 사후 제출/채택 기록은 v0.3 `SubmissionRecord` 신설 예정.

#### 5.2.7 `chat.py` — Step3 보완 대화

`/api/chat/draft-assist` — Step3 inline 편집 중 "이 부분 다시 써줘" 같은 보완 대화.

#### 5.2.8 기타

- `bookmarks.py` — 공고 북마크
- `profile.py` — V1 기업 프로필 (settings)
- `diagnosis.py` — 완성도 진단
- `ai.py` — V1 AI wrapper (deprecated)

### 5.3 services/ 상세

#### 5.3.1 AI Provider 계층

```
AIProvider (abstract)
├─ MockProvider          ← 개발/테스트용 가짜 응답
├─ OpenAIProvider        ← gpt-4o, gpt-4o-mini, gpt-4o-form_parser
├─ AnthropicProvider     ← Claude Haiku, Sonnet, Opus
└─ LocalProvider         ← LM Studio (gemma, qwen 등)
```

선택 규칙:
- `.env`의 `AI_PROVIDER` 변수 (`mock` | `openai` | `anthropic` | `local`)
- `get_provider()` factory가 분기

호출 메서드 8종 (PRD §14.2):
```
provider.notice_analyst(text)
provider.form_parser(text, form_name)
provider.company_analyzer(company_files, notice_schema)
provider.evidence_extractor(text, source_file)
provider.draft_writer(question, mapping_result, evidence, ...)
provider.draft_evaluator(drafts, notice_schema)
provider.missing_material(question, evidence)
provider.draft_rewriter(current_text, feedback)
```

#### 5.3.2 FormParser 파이프라인 (FormParser v2)

```
PDF
  ↓ pdfplumber + pypdfium2
form_layout_builder.py
  ↓ Layout IR (pages/blocks/tables/cells_raw)
form_llm_input_builder.py
  ↓ Semantic Markdown ("<EMPTY_FIELD id=...>", "[ ]" 체크박스)
form_parser LLM
  ↓ FormSchema (raw)
table_normalizer.py (header_path, title_candidate)
  ↓
table_promoter.py (LLM 누락 표 자동 승격 + cell grid)
  ↓
form_parser_postprocessor.py (parser hint 주입)
  ↓
quality_metrics + repair pass
  ↓
DB 영속화 (form_schema_json.schema)
```

옵션 (b4-8.md §3.10):
- `FORM_NORMALIZE_TABLE=true` — table_normalizer 실행
- `FORM_AUTO_PROMOTE_TABLE=true` — table_promoter 실행
- `FORM_PARSER_DEBUG=true` — `backend/data/sessions/.../debug/` 산출물 생성

#### 5.3.3 Hybrid form_parser

`form_parser_hybrid.py` — 큰 PDF (>30K tokens) TPM 회피용.
1. regex로 챕터 split (`1. 사업개요` / `2. 추진계획` 패턴)
2. chunk별 병렬 LLM 호출 (asyncio.gather)
3. merger가 question_id 재할당 + 섹션 통합

frontend `backendApi.js`의 `parseForm({ parserMode: 'hybrid' })` 가 기본값.

#### 5.3.4 Evidence pipeline

```
참고자료 PDF/DOCX
  ↓ files.py parse_upload_bytes
evidence_chunker.py
  ↓ chunk split (512 token 단위)
evidence_embedder.py
  ↓ embedding (bge-m3-ko or openai-large)
evidence_store.py
  ↓ ChromaDB persistent (backend/chroma_data/)

문항 query
  ↓ item_query_builder.py
evidence_matcher.py (BM25 + 임베딩)
  ↓
mapping_pipeline.py (BackgroundTasks)
  ↓
MappingResult per question
```

#### 5.3.5 LLM 안전망

- `llm_response_parser.py` — JSON 코드펜스 제거, `validate_used_evidence_ids()` 환각 ID 차단
- `llm_token_budget.py` — context overflow 방지 (Sonnet 200K)
- `audit_logger.py` — 모든 LLM 호출 로그 (`ai_call_logs` 테이블)
- `ai_cost.py` — 단가표 (config/pricing.json) 기반 KRW 계산

#### 5.3.6 LM Studio Client (2026-05-25 신규)

`services/lm_studio_client.py`:

```python
async def call_lm_studio(system, user, *, max_tokens=4096, temperature=0.2):
    """gemma-4-e4b reasoning 모델 대응:
       - reasoning_content + content 분리 응답
       - max_tokens 충분히 (4096) 잡아야 빈 응답 안 남
       - finish_reason='length' + content="" 시 명확한 에러
    """
```

DetailPage `/api/notices/extract-structured` 에서 사용.

### 5.4 ontology/schemas.py — Pydantic 11종

```python
class ApplicationSession  # 작업 단위 (모든 산출물의 부모)
class CompanySchema       # 기업 정보 + 분석 결과
class NoticeSchema        # 공고 분석 결과 (target/benefit/eligibility/...)
class FormSchema          # 제출양식 구조 (sections → questions → table_schema)
class FormQuestion        # 단일 문항 (title/requirement/fill_mode/table_columns/table_cell_hints)
class FormSection         # 섹션
class EvidenceSchema      # 참고자료 evidence
class MappingResult       # 문항 ↔ Evidence 매칭
class MissingMaterial     # 부족자료 상태
class SupplementalMaterial# 사용자 보완자료 원본
class DraftItem           # 작성된 초안
class FitAnalysis         # 공고 적합성 (3축)
class EvalCriteriaMapping # 평가기준 ↔ 문항 매핑
class CompanyFile         # 기업프로필 자료 메타 (A3)
```

### 5.5 migrations/ — 5개 idempotent 마이그레이션

| 파일 | 내용 |
|------|------|
| 0001_draft_version.py | drafts 테이블 version 컬럼 + backup table |
| 0002_audit_log.py | ai_call_logs 테이블 신설 |
| 0003_v02_schema.py | v0.2 ontology 11종 테이블 |
| 0004_company_file_parsed_text.py | company_files에 parsed_text 등 7 컬럼 ADD |
| 0005_eval_criteria_history.py | eval_criteria_mappings.history JSON ALTER ADD |

실행: 자동 (`main.py`에서 `Base.metadata.create_all()` 후 migration script 호출 X — SQLAlchemy declarative 기반). Schema 변경 시 새 `00NN_*.py` 추가 + `models.py` 수정.

### 5.6 prompts/ — LLM 시스템 프롬프트

| 파일 | 사용처 |
|------|--------|
| form_parser.md (v1.4) | provider.form_parser() — 제출양식 분석 |
| notice_analyst.md | provider.notice_analyst() — 공고 분석 |
| company_analyzer.md | provider.company_analyzer() — 기업 분석 |
| draft_writer.md | provider.draft_writer() — 초안 작성 |
| draft_evaluator.md | provider.draft_evaluator() — 평가 |
| missing_material.md | 부족자료 추출 |
| draft_rewriter.md | 사용자 피드백 재작성 |
| eval_criteria_mapper.md | 평가기준 매핑 |

수정 시 fixture (`tests/fixtures/llm_responses/*.json`) 도 함께 업데이트 필요.

### 5.7 hwpx/ — HWP/HWPX 모듈 (2026-05-25 통합)

#### `hwp_reader.py`

```python
def read_hwp(filepath, debug=False) -> List[str]:
    """파일 경로 → 텍스트 줄 리스트"""

def read_hwp_bytes(content: bytes, debug=False) -> List[str]:
    """bytes → 텍스트 (multipart upload 통합용)"""
```

내부 동작:
1. `olefile.OleFileIO` 로 OLE 컨테이너 열기
2. `BodyText/Section{N}` 스트림 순회
3. `zlib.decompress(raw, -15)` 압축 해제
4. 레코드 단위로 `HWPTAG_PARA_TEXT` (0x43) 추출
5. UTF-16LE 디코딩 + 컨트롤 코드 처리 (0x06 줄나눔, 0x09 탭 등)

#### `hwpx_writer.py`

```python
def save_hwpx(output_path: str, lines: list) -> None:
    """텍스트 줄 → HWPX 파일로 저장"""

def save_hwpx_bytes(lines: list) -> bytes:
    """텍스트 줄 → HWPX 파일 bytes 반환 (StreamingResponse용)"""
```

내부 동작:
1. 템플릿 `this_is_hwpx.hwpx` 열기 (zipfile)
2. `Contents/section0.xml` 의 `<hp:t>...</hp:t>` 첫 줄 교체
3. 나머지 줄은 `<hp:p>` 문단으로 `</hs:sec>` 앞에 삽입
4. zip으로 패킹 + `mimetype` 만 `ZIP_STORED` (HWPX 사양)

### 5.8 tests/

pytest 실행:
```powershell
cd backend
python -m pytest tests/ -v
```

주요 테스트:
- `test_smoke.py` — session/parse/mapping/missing/draft/export 기본 흐름
- `test_b1_confirm_step2.py` — Step2 confirm
- `test_c3_mapping_pipeline.py` — mapping pipeline e2e
- `test_a3_*.py` — Layout audit (form_layout_builder)
- `test_openai_notice_analyst.py` — 실 OpenAI 호출 (skip 가능)

fixture:
- `tests/fixtures/llm_responses/*.json` — 8개 LLM 응답 sample (form_parser/notice_analyst/draft_writer/...)
- Pydantic schema 통과 검증 자동화

### 5.9 환경변수 (backend/.env)

자세한 내용은 [§9](#9-환경변수-레퍼런스) 참조. 주요:

```ini
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL_ANALYSIS=gpt-4o-mini
OPENAI_MODEL_FORM_PARSER=gpt-4o
OPENAI_MODEL_DRAFT=gpt-4o-mini

LM_STUDIO_URL=http://127.0.0.1:1234
LM_STUDIO_MODEL=google/gemma-4-e4b
LM_STUDIO_TOKEN=sk-lm-...

DATABASE_URL=sqlite:///./ajin.db
APP_ENV=development
CORS_ALLOWED_ORIGINS=

FORM_NORMALIZE_TABLE=true
FORM_AUTO_PROMOTE_TABLE=true
ALLOW_PRECONFIRM_PRECHECK=false
```

---

## 6. 프론트엔드 상세 가이드

### 6.1 main.jsx — React entry

```jsx
import { BrowserRouter } from 'react-router-dom'
import App from './App'

createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>
)
```

### 6.2 App.jsx — ★ 라우팅 + 전역 state (1000+ 줄)

핵심 책임:
1. **라우트 정의** — react-router 7 `<Routes>`
2. **전역 state** — settings, bookmarks, drafts, notices, selectedNotice, view
3. **세션 복원** — sessionStorage(`ajin_v2_session_id`) 기반
4. **setView 분기** — 'draft'/'resumeDraft'/'library' 특수 처리

라우트 목록:
```
/                  → DashboardPage
/dashboard         → DashboardPage
/search            → SearchPage
/detail            → DetailPage
/draft             → DraftPage (V1, AI_DEV_MODE=false 시)
/draft-v2          → DraftPageV2 (V2, AI_DEV_MODE=true 시)
/draft-list        → DraftListPage
/myDrafts          → MyDraftsPage
/library           → MaterialsLibraryPage (2026-05-25 신규)
/bookmark          → BookmarkPage
/notification      → NotificationPage
/notiSettings      → NotificationSettingsPage
/settings          → SettingsPage
/archive           → ArchivePage
```

`setView()` 분기 (2026-05-25 갱신):
```js
const setView = (v) => {
  if (v === 'draft') {
    // '신규 작성' — 항상 신규 세션 시작
    sessionStorage.removeItem(V2_SESSION_STORAGE_KEY)
    setSelectedNotice(null)
    navigate(DRAFT_DEFAULT_ROUTE)
    return
  }
  if (v === 'resumeDraft') {
    // '초안 이어 작성' — 가장 최근 in-progress 세션 복원
    const recent = displayDrafts.find((d) => d._isV02 && d._sessionId)
    if (!recent) { alert('작성 중인 초안이 없습니다.'); return }
    sessionStorage.setItem(V2_SESSION_STORAGE_KEY, recent._sessionId)
    setSelectedNotice(null)
    navigate(DRAFT_DEFAULT_ROUTE)
    return
  }
  if (v === 'library') { navigate('/library'); return }
  navigate('/' + v)
}
```

### 6.3 api/ — 백엔드 클라이언트

#### `backendApi.js`

여러 API 객체 export:
- `noticesApi` — V1 notices
- `draftsApi` / `legacyDraftsApi` — V1 drafts
- `bookmarksApi` — 북마크
- `profileApi` — V1 프로필
- `aiApi` — V1 AI 호출
- `analysisApi` — ★ V2 분석 (parseNotice/parseForm/extractEvidence/analyzeCompany/writeDraftItem/evaluateDraft/exportDocx/listSessions/getSession/deleteSession/patchFormSchema*/getMappingStatus 등 20+ 메서드)
- `libraryApi` — 자료실 (list/get/upload/remove)
- `companyApi` — CompanyFile
- `chatApi` — Step3 draft-assist

#### `noticesApi.js`

`fetchAllNotices()` — backend `/api/notices/search` 호출 → dedupe + 마감 지난 공고 drop.

```js
function dropExpired(notices) {
  const todayStart = new Date()
  todayStart.setHours(0, 0, 0, 0)
  return notices.filter((n) => {
    if (!n.date) return true
    const t = new Date(n.date).getTime()
    return Number.isNaN(t) || t >= todayStart.getTime()
  })
}
```

> 2026-05-25 변경: backend 실패 시 MOCK_NOTICES 폴백 제거. 빈 배열 + 에러 메시지만 반환.

#### `lmStudioApi.js`

브라우저에서 직접 LM Studio (또는 OpenAI/Anthropic) 호출. 우선순위:
1. `VITE_OPENAI_API_KEY` → OpenAI gpt-4o-mini
2. `VITE_ANTHROPIC_API_KEY` → Anthropic Claude Haiku
3. 둘 다 없으면 → LM Studio (`/proxy/lmstudio`)

함수 목록:
- `generateNoticeSummary` — 4문장 요약
- `generateNoticeShortSummary` — 3줄 요약 (search 카드용, maxTokens=2048 — reasoning 모델 대응)
- `analyzeNoticeStructure` — 항목 추출
- `generateDraftSection` — 항목별 초안
- `reviseDraftSection` — 항목 수정
- `generateDraftWithLM` — 전체 일괄
- `analyzeUploadedDocument` — 업로드 문서 → JSON 추출
- `generateSubmissionDraft` — 제출 서류 초안
- `chatWithDraftReviewer` — 챗봇
- `checkUploadCompleteness` — 충족도
- `evaluateDraft` — 평가
- `applyImprovement` — 보완안 적용

### 6.4 features/layout

#### Sidebar.jsx

좌측 사이드바. 2개 카드:
1. **기업 프로필 카드** — 회사명/분야/매출/근로자/분류
2. **작성 중인 공고 카드** — 최근 in-progress 세션 5개
   - `analysisApi.listSessions` 결과 (v02Drafts)
   - 각 카드: 제목 / STEP{N} · 라벨 / 진행률 bar / 시간 / X 버튼
   - X 버튼: `analysisApi.deleteSession` (soft delete)
   - timeAgo: ISO string 처리 + NaN 가드

#### TopNav.jsx

상단 메뉴 11개:
- 대시보드 / 공고 검색 / 공고 상세(disabled) / **신규 작성** / **초안 이어 작성** / 내 사업계획서 / **자료실** / 북마크 / 맞춤 알림 / 알림 설정 / 기업 설정

### 6.5 features/notices

#### hooks/useNotices.js

`useNotices()` — backend 호출 + state 관리.

#### components/FileViewer.jsx

PDF / 이미지 / HWP-DOC-Excel-archive 분기. HWP/DOC/Excel 등은 `UnsupportedView`:
- 다운로드 버튼
- **HWP만** 추가: "본문 추출" 버튼 → backend `/api/files/prefetch-url` 호출 → text 미리보기

#### utils/

- `normalize.js` — bizinfo/k-startup URL을 Vite proxy 경로로 변환 + 첨부파일 파싱
- `filtering.js` — applyFilters (키워드/지역/규모/매칭 모드/임계값)
- `date.js` — parseDate / formatDate / getDdayText
- `match.js` — buildNoticeCorpus / similarityScore

### 6.6 features/pages

#### DashboardPage.jsx

수치 요약 카드 + 최근 공고 + 작성 중 세션.

#### SearchPage.jsx

필터 패널 (4 grid) + 카테고리 toggle + 정렬 + 출처 필터 + 탭(카드/리스트/일정) + 페이지네이션. 카드별 "3줄 요약 보기" 버튼 → `generateNoticeShortSummary` 호출.

#### DetailPage.jsx

공고 상세 카드 (타이틀/지원대상/지원내용/혜택/유의사항/일정/문의처/첨부파일) + **AIExtractCard** (2026-05-25 신규):

```jsx
function AIExtractCard({ attachments, notice }) {
  // 첫 번째 첨부파일 prefetch + extract-structured 호출
  // 결과를 ResultCell 그리드로 표시 (10개 항목)
}
```

#### DraftPage.jsx (V1 legacy)

`/draft` 라우트. 5단계 진단 + 초안 자동 생성. Step5 export:
- TXT / **HWPX** (2026-05-25 추가) / DOCX

#### DraftPageV2 (`draft-v2/`)

`/draft-v2` 라우트. ★ 메인 워크플로. [§7](#7-초안-작성-흐름-step-1-5) 자세히.

#### MaterialsLibraryPage.jsx (2026-05-25 신규)

자료실 페이지:
```
[업로드 영역 — 카테고리 선택 + multi-file]
[정렬: 최근 업데이트순 ▼ | 이름순]
[전체] [회사 자료] [첨부 자료] [필요 자료]
┌─ 파일 리스트 ──────────────────────────┐
│ icon  파일명  카테고리  업로드일  🗑   │
└─────────────────────────────────────────┘
[우측: 파일 상세 패널 (parsed_text preview)]
```

#### SettingsPage.jsx

기업 프로필 입력 (기본/업종/규모/매출/팀/전략). 2026-05-25 신규: **CompanyMaterialsCard** — 회사 자료 업로드 + 기업 분석 + 자료실 연동.

### 6.7 features/draft-upload

#### Step1Common.jsx

Step1 자료 업로드. V1/V2 공용. 카드 4개:
1. 공고문 파일 — 업로드 또는 "자동 첨부" 안내
2. 제출양식 파일
3. 참고자료 (여러 개)
4. 기업프로필 자료 — `companyApi.list()` 호출 (선택만, 업로드 X — 기업 설정 페이지에서)

`analysisApi.createSession` → sessionStorage 설정 → `analysisApi.files` (multipart 업로드) → Step2 진입.

### 6.8 features/drafts

- `MyDraftsPage.jsx` — 제출 이력 (V1 drafts 테이블)
- `ArchivePage.jsx` — 보관함

### 6.9 components/ui (shadcn)

```
Button / Card / CardContent / CardHeader / CardTitle
Input / Textarea / Label / Select / Separator
Badge / Alert / AlertDescription
Tooltip / Tabs / Toast / Dialog
```

`lib/utils.js` 의 `cn()` 으로 Tailwind class merge.

### 6.10 vite.config.js — Proxy 설정

```js
'/api'             → :8000 (FastAPI)
'/proxy/bizinfo'   → bizinfo.go.kr
'/proxy/apis'      → apis.data.go.kr
'/proxy/bizfiles'  → bizinfo.go.kr (첨부)
'/proxy/kstartupfiles' → k-startup.go.kr (첨부)
'/proxy/lmstudio'  → 127.0.0.1:1234 (+Authorization Bearer 자동 주입)
```

LM Studio token은 `.env.server`에서 읽어옴 (dotenv).

---

## 7. 초안 작성 흐름 (Step 1~5)

### 7.1 전체 흐름

```
사용자 클릭 "신규 작성"
  ↓
URL: /draft-v2
DraftPageV2.jsx 진입
  ↓
sessionStorage.ajin_v2_session_id 확인
  ├─ 없음 → Step1 자료 업로드 (신규 세션)
  └─ 있음 → backend /api/analysis/sessions/{id} 조회 → 복원
            └─ session.current_step 으로 점프

[Step1] 자료 업로드
  → Step1Common.jsx
  → analysisApi.createSession({ user_id: 'anonymous', notice_id })
  → multipart 업로드 (공고/양식/참고/기업자료)
  → currentStep = 2

[Step2] 분석
  → Step2Analysis.jsx
  → Tab1 "공고문 분석" + Tab2 "제출양식 분석"
  → 자동 트리거: parseNotice / parseForm / extractEvidence / analyzeCompany (병렬)
  → 사용자 확인 후 "Step 2 분석 결과 확정 →" 클릭
  → POST /api/analysis/confirm-step2 → confirmed_form_schema 저장
  → currentStep = 3

[Step3] 초안 작성
  → Step3Draft.jsx
  → 좌 트리 (FormTreePanel) — 섹션/문항 클릭
  → 우 편집 (textarea + table grid + AI 초안 생성 버튼)
  → POST /api/analysis/write-draft-item per question
  → DraftItem.status = approved 시 다음 진행
  → currentStep = 4

[Step4] 평가
  → Step4Evaluation.jsx
  → POST /api/analysis/evaluate-draft
  → 평가 점수 + 카테고리 + 보완 제안 표시
  → currentStep = 5

[Step5] Export
  → Step5Export.jsx
  → POST /api/analysis/export-docx (mock)
  → 또는 POST /api/files/export-hwpx → .hwpx 다운로드
  → currentStep = 6 (completed)
```

### 7.2 DraftPageV2.jsx (컨테이너)

핵심 책임:
1. sessionId 관리 (sessionStorage)
2. notice 복원 (notice_id mismatch 검사)
3. 5개 Step 컴포넌트 분기 (currentStep)
4. drafts_preservation_policy 모달 (Step3 → Step2 backward 시)
5. step2Data lift (Step2 분석 결과를 Step3+에 전달)

```jsx
const [sessionId, setSessionId] = useState(() => sessionStorage.getItem(V2_SESSION_STORAGE_KEY))
const [restoredFormSchema, setRestoredFormSchema] = useState(null)
const [restoreChecked, setRestoreChecked] = useState(false)

useEffect(() => {
  if (!sessionId) return
  analysisApi.getSession(sessionId).then(res => {
    setRestoredFormSchema(res.form_schema_json?.schema)
    setRestoreChecked(true)
  })
}, [sessionId])
```

### 7.3 Step1 — 자료 업로드

`features/draft-upload/Step1Common.jsx`

4개 영역:
- **공고문 (notice)** — Notice 객체에서 자동 첨부 또는 사용자 업로드
- **제출양식 (form)** — PDF/HWP/DOCX 업로드 필수
- **참고자료 (references)** — 여러 개 가능. 영속화는 client-side memory만 (A3 후속 부채)
- **기업 자료 (companyFiles)** — `companyApi.list()` 결과에서 선택. 업로드는 기업 설정 페이지에서

업로드 시 즉시 `analysisApi.files` 호출 → parsed_text 추출 → `notice_schema_json.attachments` JSON-piggyback 영속화.

### 7.4 Step2 — 분석

`features/pages/draft-v2/Step2Analysis.jsx` (★ 2000+ 줄)

2 탭:

#### Tab1 — 공고문 분석

좌측: 분석 결과 (지원대상/지원내용/평가기준)
우측: PDF 미리보기

상단 액션:
- ↻ 공고문 다시 분석 (parse-notice 재호출)

#### Tab2 — 제출양식 분석

3분할 (좌/중/우):
- 좌: **FormTreePanel** — 섹션/문항 트리, 클릭 시 PDF 페이지 점프
- 중: **FormPreviewPanel** — PDF 미리보기 (페이지 네비 wrap-around)
- 우: **SupplementalPanel** — 선택 문항 세부 + cell grid (Option C)

상단 액션:
- ↻ 양식 다시 분석 (parse-form 재호출, parser_mode 선택 가능)

#### 자동 트리거 흐름

```js
Promise.allSettled([
  analysisApi.parseForm({ sessionId, formText, parserMode: 'hybrid' }),
  analysisApi.extractEvidence({ sessionId, refText }),
  analysisApi.analyzeCompany({ sessionId, companyFiles, noticeSchema }),
]).then(([formRes, evidenceRes, companyRes]) => {
  if (formRes.status === 'fulfilled') {
    setFormApiResp(formRes.value)
    setFormData(adaptFormFromApi(formRes.value))
  } else {
    handleFallback('parse-form', formRes.reason, { onError: setFormError })
  }
  // ...
})
```

병렬 호출. 실패 시 `handleFallback` (lib/runtimeLog.js)가 에러 토스트.

#### FormSchema edit UI v0.1

`FormTreePanel.jsx` 의 hover 버튼 3종:
- **✏️ 편집** — `FormQuestionEditor` 모달 (title/source_page/is_required/...)
- **+ 추가** — 섹션 아래에 새 문항 (USER-{uuid8} ID)
- **🚫 제외** — `excluded_question_ids` 토글 (회색 + "작성 제외" 배지)

backend PATCH `/api/analysis/form-schema/question` 호출.

### 7.5 Step2 DevMode (개발자 모드)

`Step2DevMode.jsx` — 7 Tab:
- Tab1 — 분석 통계
- Tab2 — FormSchema 트리
- Tab3 — Validation (미연결)
- Tab4 — Evidence 매핑
- Tab5 — Company fit
- Tab6 — Mapping result
- Tab7 — Settings (모델 선택, 미연결)

parser_mode 토글 (single / hybrid).

### 7.6 Step3 — 초안 작성

`Step3Draft.jsx`

좌 트리 + 우 편집기:
- 트리 클릭 → 해당 문항 선택
- 우 편집:
  - 문항 메타 (title / requirement / writing_guidelines)
  - mapping_result (used_evidence_ids 카드)
  - 초안 textarea (사용자 inline 편집)
  - "AI로 초안 작성" 버튼 → `analysisApi.writeDraftItem`
  - 표 항목이면 cell grid 표시 (Option C: header_cells / data_rows)

상태:
- `draft` — 작성 중
- `approved` — 사용자 확정
- `excluded` — 제외 (Step2에서 🚫)
- `needs_revision` — 평가 후 보완 필요

### 7.7 Step4 — 평가

`Step4Evaluation.jsx`

평가 결과:
- 종합 점수 (currentScore)
- 카테고리별 점수 (기술성/사업성/기대효과/수행역량)
- topIssues — 우선순위별 보완 제안
- improvementProgress — 적용/진행/대기

`POST /api/analysis/evaluate-draft` 호출.

### 7.8 Step5 — Export

`Step5Export.jsx`

옵션:
- include_table_data (체크)
- 출처 표시 방식 (UI만)

다운로드:
- DOCX (현재 mock URL — Phase 4-G 후반 실구현)
- HWPX (실구현 — `/api/files/export-hwpx`)
- TXT (legacy `DraftPage.jsx` 에서만)

미작성 항목이 있어도 export 가능 (PRD §8 "부족해도 1차 초안" 정신).

### 7.9 데이터 영속화 정책

| 데이터 | 위치 | 캐시 우선순위 |
|--------|------|--------------|
| NoticeSchema | `notice_schema_json.schema` | DB > sessionStorage > EMPTY |
| FormSchema | `form_schema_json.schema` | DB > sessionStorage > EMPTY |
| Notice/Form 첨부 메타 | `*_schema_json.attachments` (JSON-piggyback) | DB only |
| Notice/Form parsed_text | 첨부 메타 안 (≤200K) | DB only |
| 참고자료 (reference) | client-side memory만 | (A3 후속 부채) |
| 기업 자료 | `company_files` 테이블 + 디스크 BLOB | DB only |
| EvidenceItem | `evidence_items` 테이블 + ChromaDB | DB |
| MappingResult | `mapping_results` 테이블 | DB |
| DraftItem | `draft_items` 테이블 | DB |
| EvalCriteriaMapping | `eval_criteria_mappings` 테이블 + history JSON | DB |

`MOCK_*` 자동 사용 금지 — DB/cache 둘 다 없으면 빈 상태 표시.

### 7.10 V1 vs V2 정책

| 항목 | V1 (`/draft`) | V2 (`/draft-v2`) |
|------|--------------|------------------|
| 데이터 | `drafts` 테이블 | `application_sessions` + 11종 ontology |
| 페이지 | DraftPage.jsx | DraftPageV2.jsx |
| 상태 관리 | useDrafts hook | sessionStorage + getSession |
| AI 호출 | `/api/ai/*` (deprecated) | `/api/analysis/*` |
| Export | TXT/DOCX/HWPX | DOCX (mock) + HWPX + TXT |
| 진입 | TopNav '신규 작성' (운영) | TopNav '신규 작성' (DEV_MODE=true) |

V1은 legacy 유지 (CLAUDE.md §4 보호). V2가 신규 작업의 주 흐름.

---

## 8. 자료실 + AI 본문 분석

### 8.1 자료실 (Materials Library)

#### 사용 시나리오

1. **회사 자료 영구 저장** — 회사소개서, 재무제표, 사업자등록증 등 여러 사업계획에서 재사용
2. **공고별 첨부 자료** — 특정 공고에 필요한 추가 자료
3. **필요 자료 체크리스트** — 부족자료 추적

#### 진입

- TopNav **'자료실'** 클릭 → `/library`
- 또는 기업 설정 페이지의 `CompanyMaterialsCard` 에서 회사 자료 업로드 시 자동 반영

#### 동작

1. **업로드** — multi-file, 카테고리 선택 (회사자료/첨부자료/필요자료)
2. **자동 텍스트 추출** — backend `parse_upload_bytes`:
   - PDF → pdfplumber
   - DOCX → python-docx
   - **HWP → olefile + zlib + 레코드 파싱** (2026-05-25 통합)
   - XLSX/CSV → pandas
   - TXT → utf-8-sig
3. **DB 영속화** — `company_files.parsed_text` (≤200K chars cap)
4. **리스트** — 카테고리 필터 + 정렬 (최근/이름)
5. **상세 패널** — parsed_text preview (500자 + 전체 보기)
6. **soft delete** — `status='deleted'` 변경

#### Backend 구조

| 컬럼 | 값 |
|------|-----|
| file_type | "회사자료" / "첨부자료" / "필요자료" / legacy (회사소개서/재무제표/...) |
| parsed_text | 텍스트 전문 (≤200K) |
| parsed_text_truncated | bool — 자름 여부 |
| char_count | 원본 전체 길이 |
| file_storage_path | `company/{profile_id}/{file_id}.{ext}` |

`/api/library/files?category=회사자료` 는 legacy file_type까지 IN 절로 포함.

### 8.2 DetailPage AI 본문 분석 (2026-05-25 신규)

#### 사용 시나리오

공공데이터 API에서 받은 공고 메타(target/benefit/documents 등)가 빈 값이거나 부정확할 때, 첨부파일(공고 PDF/HWP)을 AI가 분석해 각 칸을 자동 채움.

#### 동작

1. **DetailPage 진입** — 첨부파일 1개 이상 있으면 `<AIExtractCard>` 표시
2. **"첨부파일 → 각 칸 자동 채우기" 버튼 클릭**
3. **Backend prefetch** — `POST /api/files/prefetch-url` → 외부 URL 다운로드 + parse_upload_bytes
4. **LLM 분류** — `POST /api/notices/extract-structured` → LM Studio (`google/gemma-4-e4b`)
5. **결과 카드 그리드** — 10개 항목 표시
   - 공고 제목 / 지원 대상 / 지원 내용 / 제출 서류 / 신청 기간 / 마감일 / 지역 / 제한 사항 / 사업 개요 / 문의처

#### URL Protocol 주의 (2026-05-25 수정)

`attachment.url` 은 Vite proxy 경로(`/proxy/bizfiles/...`) — backend는 이걸 다운로드 못 함. **`attachment.originalUrl`** (절대 URL) 을 backend에 전달해야 함.

```js
const backendUrl = file.originalUrl || file.url
fetch('/api/files/prefetch-url', { body: JSON.stringify({ url: backendUrl, filename: file.name }) })
```

Backend에도 안전망 — protocol 없는 url이면 422 명확 에러.

#### LM Studio Reasoning 모델 주의

`google/gemma-4-e4b` 는 reasoning(thinking) 모델 — 응답이 `reasoning_content` + `content` 두 부분. max_tokens 충분히 (≥4096) 잡지 않으면 reasoning에서 다 소진되어 `content=""` + `finish_reason="length"` 빈 응답.

`services/lm_studio_client.py` 가 명확한 에러 raise + max_tokens=4096 기본.

### 8.3 HWP 파일 통합 (2026-05-25 신규)

#### 입력 (HWP 추출)

`backend/hwpx/hwp_reader.py`:
- `read_hwp(filepath)` — 파일 경로
- `read_hwp_bytes(content)` — bytes (multipart upload용)

자료실, Step1 업로드, DetailPage 첨부파일 prefetch 어디서든 자동 추출.

지원 안 되는 케이스 — UTF-16 서로게이트, 일부 컨트롤 코드는 무시.

#### 출력 (HWPX 생성)

`backend/hwpx/hwpx_writer.py`:
- `save_hwpx(output_path, lines)` — 파일 저장
- `save_hwpx_bytes(lines)` — bytes 반환

템플릿 `this_is_hwpx.hwpx` 사용. 첫 줄은 템플릿의 `<hp:t>` 교체, 나머지 줄은 새 `<hp:p>` 문단 추가.

#### Export 흐름

```
Step5 (또는 V1 DraftPage) ".HWPX 다운로드" 버튼
  ↓
backendApi 호출 (POST /api/files/export-hwpx)
  Body: { lines: ["[1. 사업 개요]", "본 사업은 ...", ...], filename: "사업계획서.hwpx" }
  ↓
backend save_hwpx_bytes(lines)
  ↓
StreamingResponse (Content-Disposition: attachment; filename*=UTF-8'' + 한글)
  ↓
브라우저 다운로드
```

### 8.4 PDF 뷰어 hwp 메시지 (2026-05-25 추가)

PDF 뷰어가 hwp 파일 로드 실패 시 메시지:
- 일반: "PDF를 불러올 수 없습니다"
- hwp 확장자: "hwp 파일을 불러올 수 없습니다" (`FileViewer.jsx:138` regex 분기)

---

## 9. 환경변수 레퍼런스

### 9.1 backend/.env

#### AI Provider 선택

```ini
AI_PROVIDER=openai           # hybrid | mock | openai | anthropic | local
AI_COST_MODE=balanced        # balanced | cost_save | quality_first
```

#### OpenAI

```ini
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL_ANALYSIS=gpt-4o-mini
OPENAI_MODEL_DRAFT=gpt-4o
OPENAI_MODEL_FORM_PARSER=gpt-4o
OPENAI_PRICING_PATH=                 # (선택) services/ai_cost.py 단가표
```

> form_parser는 입력이 큼 (~37K tokens, 38페이지 form 기준). gpt-4o TPM(30K) 초과 시 → hybrid mode 또는 gpt-4o-mini 권장.

#### Anthropic

```ini
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL_HAIKU=claude-haiku-4-5
ANTHROPIC_MODEL_SONNET=claude-sonnet-4-6
ANTHROPIC_MODEL_OPUS=claude-opus-4-7    # premium_final_writer 전용
```

#### LM Studio (Local LLM)

```ini
LM_STUDIO_URL=http://127.0.0.1:1234
LM_STUDIO_MODEL=google/gemma-4-e4b      # reasoning 모델 — max_tokens 충분히
LM_STUDIO_TOKEN=sk-lm-...               # LM Studio에서 인증 활성 시
LOCAL_LLM_URL=http://localhost:1234/v1  # 별도 local provider용 (AI_PROVIDER=local)
LOCAL_LLM_MODEL=local-model
```

#### 임베딩 / Vector Store

```ini
EMBEDDING_MODEL=bge-m3-ko               # bge-m3-ko | openai-large
EMBEDDING_URL=http://localhost:11434
VECTOR_STORE=sqlite                     # sqlite | pgvector (v0.3)
```

#### 비용 한도

```ini
DAILY_COST_LIMIT_KRW=10000
MONTHLY_COST_LIMIT_KRW=300000
PRICING_CONFIG_PATH=../config/pricing.json
```

#### 매칭

```ini
DEFAULT_MATCHING_THRESHOLD=0.70
```

#### DB

```ini
DATABASE_URL=sqlite:///./ajin.db        # v0.2 = sqlite
```

#### FormParser 기능 토글

```ini
FORM_NORMALIZE_TABLE=true               # table_normalizer
FORM_AUTO_PROMOTE_TABLE=true            # table_promoter
ALLOW_PRECONFIRM_PRECHECK=false         # production false 고정
```

#### CORS

```ini
APP_ENV=development                     # development | production
CORS_ALLOWED_ORIGINS=                   # production 필수, 쉼표 구분
# 예시: CORS_ALLOWED_ORIGINS=https://your.com,https://www.your.com
```

#### Mock Policy

```ini
MOCK_MODE=false                         # true일 때만 MockProvider (현재 미적용)
DISABLE_MOCK_FALLBACK=true              # AI 실패 시 Mock 폴백 금지 (현재 미적용)
```

### 9.2 web-react/.env

```ini
VITE_API_BASE_URL=http://localhost:8000
VITE_ENABLE_ANALYSIS_DEV_MODE=true      # /draft-v2 활성화
VITE_DISABLE_MOCK_FALLBACK=false        # true: API 실패 시 mock 폴백 차단

VITE_API_KEY=YOUR_API_KEY               # 공공데이터 포털 키
VITE_BIZ_KEY=YOUR_BIZ_KEY               # 기업마당 키

VITE_BIZINFO_API_URL=https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do
VITE_MSIT_API_URL=https://apis.data.go.kr/1721000/...
VITE_MSS_API_URL=https://apis.data.go.kr/1421000/...
VITE_KSTARTUP_API_URL=https://apis.data.go.kr/B552735/...
VITE_NOTICE_SEARCH_NM=자동차

VITE_ENABLE_DEMO_NOTICES=false          # 2026-05-25 — 사용 안 함 (DEMO_NOTICES 제거)

# LM Studio 직접 호출용 (선택, 보통 .env.server 사용)
VITE_LM_STUDIO_URL=
VITE_LM_STUDIO_TOKEN=
VITE_USE_MOCK=false                     # production safe

# 외부 LLM API (있으면 LM Studio 대신 사용)
VITE_OPENAI_API_KEY=
VITE_ANTHROPIC_API_KEY=
```

> **⚠ VITE_* 는 브라우저 번들에 포함됨** — 민감 정보는 `.env.server` 에 두고 server.js / vite.config.js proxy 에서만 사용.

### 9.3 web-react/.env.server (Production 서버 + LM Studio Token)

```ini
API_KEY=<공공데이터_api_key>
BIZ_KEY=<기업마당_key>
LM_STUDIO_URL=http://127.0.0.1:1234
LM_STUDIO_TOKEN=sk-lm-...
PORT=8080
```

- `server.js` Express 서버가 dotenv 로 로딩
- `vite.config.js` 도 dotenv 로 로딩 (`/proxy/lmstudio` Bearer 헤더 주입)

---

## 10. DB 스키마 + 마이그레이션

### 10.1 테이블 목록 (16개)

#### Legacy V1 (CLAUDE.md §4 보호)

- `notices` — 공고 캐시
- `drafts` — V1 초안 (보호)
- `drafts_backup_20260507_095813` — 0001 마이그레이션 백업
- `bookmarks` — 북마크
- `profile` — V1 기업 프로필

#### Audit

- `ai_call_logs` — 모든 LLM 호출 로그 (request_id / task_type / status / duration_ms / cost_estimate_krw / error_message)

#### V0.2 Ontology (PRD §13.1)

- `application_sessions` — 작업 단위 (모든 산출물의 부모)
- `evidence_items` — 참고자료 evidence
- `mapping_results` — 문항 ↔ Evidence 매칭
- `missing_materials` — 부족자료
- `supplemental_materials` — 사용자 보완자료
- `fit_analyses` — 공고 적합성 (3축)
- `eval_criteria_mappings` — 평가기준 매핑 (history JSON 포함)
- `draft_items` — 초안

#### 운영 보조

- `company_files` — 기업프로필 자료 + 자료실 (A3-lite + 2026-05-25 자료실 통합)

### 10.2 application_sessions 핵심 컬럼

```sql
session_id                  TEXT PRIMARY KEY
user_id                     TEXT NOT NULL        -- 현재 'anonymous'
company_profile_id          TEXT
notice_file_id              TEXT                 -- 첨부 file_id (FK 없음, JSON-piggyback)
form_file_id                TEXT                 -- 양식 file_id
reference_file_ids          TEXT DEFAULT '[]'    -- JSON 배열
selected_company_file_ids   TEXT DEFAULT '[]'    -- company_files.file_id soft ref
status                      TEXT NOT NULL DEFAULT 'created'
current_step                INTEGER DEFAULT 1
notice_schema_json          TEXT DEFAULT '{}'    -- ★ NoticeSchema + attachments + parser_metadata
form_schema_json            TEXT DEFAULT '{}'    -- ★ FormSchema + confirmed_schema + parser_metadata + excluded_question_ids
company_schema_json         TEXT DEFAULT '{}'
drafts_preservation_policy  TEXT DEFAULT 'user_choice'
created_at / updated_at / last_activity_at / confirmed_step2_at / completed_at / abandoned_at / exported_at / export_count / last_export_file_id
```

### 10.3 status enum

```
created          ← 신규 (Step1 진행 중)
analyzing        ← Step2 분석 중
confirmed_step2  ← Step2 분석 결과 확정
drafting         ← Step3 작성 중
evaluating       ← Step4 평가 중
completed        ← Step5 export 완료
abandoned        ← 사용자 삭제 (soft delete)
```

### 10.4 마이그레이션 5개

자세한 SQL은 `local/2_work/db/current_database_ddl.sql` 참조.

```
0001_draft_version.py        — drafts version 컬럼 + backup
0002_audit_log.py            — ai_call_logs
0003_v02_schema.py           — v0.2 ontology 11종
0004_company_file_parsed_text.py — company_files에 parsed_text + 6개 컬럼 ADD
0005_eval_criteria_history.py — eval_criteria_mappings.history JSON ALTER ADD
```

### 10.5 Soft Reference (코드 레벨)

FK 미설정. 무결성은 코드에서 보장:

```
application_sessions.notice_file_id          → notice_schema_json.attachments[] (JSON-piggyback)
application_sessions.form_file_id            → form_schema_json.attachments[]
application_sessions.reference_file_ids[]    → (client-side only, A3 후속)
application_sessions.selected_company_file_ids[] → company_files.file_id
supplemental_materials.file_id               → (TBD)
draft_items.used_evidence_ids[]              → evidence_items.evidence_id
mapping_results.matched_evidence_ids[]       → evidence_items.evidence_id
eval_criteria_mappings.mapped_questions[]    → formSchema.questions[].id
```

### 10.6 백업

`backend/backups/ajin_NNNN_pre_YYYYMMDD_HHMMSS.db` — 마이그레이션 전 자동 백업.

복구:
```powershell
copy backend\backups\ajin_0005_pre_*.db backend\ajin.db
```

---

## 11. 외부 API + LLM 통합

### 11.1 공공데이터 API 4종

| API | URL | Key 환경변수 | 응답 형식 |
|-----|-----|-------------|----------|
| 기업마당 | bizinfo.go.kr/uss/rss/bizinfoApi.do | BIZ_KEY (crtfcKey) | XML/JSON |
| 과기부 | apis.data.go.kr/1721000/msitannouncementinfo | API_KEY (ServiceKey) | JSON |
| 중기부 | apis.data.go.kr/1421000/mssBizService_v2 | API_KEY (serviceKey) | JSON |
| K-Startup | apis.data.go.kr/B552735/kisedKstartupService01 | API_KEY (serviceKey) | JSON |

Backend `routers/notices.py:_fetch_external()` 가 4개 병렬 호출 + dedupe.

### 11.2 LLM Provider 별 사용처

```
notice_analyst       → OPENAI gpt-4o-mini (cost_save) / gpt-4o (quality_first)
form_parser          → OPENAI gpt-4o (한국어 표 인식)
evidence_extractor   → OPENAI gpt-4o-mini
company_analyzer     → OPENAI gpt-4o-mini
draft_writer         → OPENAI gpt-4o (한국어 quality) / Anthropic Sonnet 4.6
draft_evaluator      → OPENAI gpt-4o
missing_material     → OPENAI gpt-4o-mini
premium_final_writer → Anthropic Opus 4.7 (마지막 손질 단계만)

DetailPage 본문 분류 → LM Studio gemma-4-e4b (로컬)
3줄 요약            → LM Studio gemma-4-e4b (또는 OpenAI gpt-4o-mini)
```

### 11.3 LM Studio 설정 가이드

#### 설치
1. https://lmstudio.ai 다운로드
2. 모델 다운로드 — `google/gemma-4-e4b` (reasoning) 또는 `qwen2.5-7b-instruct` (instruct)
3. Server 탭 → "Start Server" → port 1234

#### 인증 토큰 (선택)
LM Studio가 토큰 요구하면 (Settings → Security) → 토큰 발급 → `LM_STUDIO_TOKEN` 환경변수.

#### Mac Mini 공유 (팀 LLM 서버)
1. Mac Mini LM Studio → "Serve on Local Network" 켜기
2. Mac Mini LAN IP 확인 (System Preferences → Network)
3. 팀원 PC의 `.env.server` 에 `LM_STUDIO_URL=http://<Mac_Mini_IP>:1234`
4. 팀원은 `node server.js` (port 8080) 또는 Vite dev mode (vite.config.js가 토큰 자동 주입)

### 11.4 비용 최적화

- `AI_COST_MODE=cost_save` — gpt-4o-mini 우선
- `AI_COST_MODE=balanced` — analysis는 mini, draft는 4o
- `AI_COST_MODE=quality_first` — 4o + premium_final_writer (Opus)
- 일별/월별 한도 — `DAILY_COST_LIMIT_KRW` / `MONTHLY_COST_LIMIT_KRW`
- OpenAI console에서 spending limit + email alert 함께 설정 권장

---

## 12. 테스트 + 검증

### 12.1 Backend (pytest)

```powershell
cd backend
python -m pytest tests/ -v
```

특정 테스트:
```powershell
python -m pytest tests/test_smoke.py::test_create_session -v
```

cover:
```powershell
python -m pytest --cov=. --cov-report=html tests/
```

### 12.2 Frontend (vitest)

```powershell
cd web-react
npm run test           # vitest run
npm run test:watch     # watch mode
```

### 12.3 E2E (Playwright)

```powershell
cd web-react
npm run e2e            # headless
npm run e2e:ui         # GUI
```

시나리오 (e2e/):
- `draft-v2-happy-path.spec.js` — Step1 업로드 → Step2 진입
- `eval-criteria-mapping.spec.js` — 평가기준 매핑
- `step2-quality-diagnostic.spec.js` — Quality Diagnostic badge

### 12.4 직접 curl 검증

#### 백엔드 헬스체크
```bash
curl http://127.0.0.1:8000/api/health
# {"status":"ok","version":"1.1.0"}
```

#### 세션 목록
```bash
curl http://127.0.0.1:8000/api/analysis/sessions?user_id=anonymous&limit=5
```

#### parse-form 직접 호출
```bash
curl -X POST http://127.0.0.1:8000/api/analysis/parse-form \
  -H "Content-Type: application/json" \
  -d '{"form_text":"1. 사업개요\n사업명: 테스트","form_name":"test.pdf","parser_mode":"single"}'
```

#### 자료실 업로드
```bash
curl -X POST http://127.0.0.1:8000/api/library/files \
  -F "file=@회사소개서.pdf" \
  -F "category=회사자료"
```

#### LM Studio 직접 호출
```bash
curl http://127.0.0.1:1234/v1/models           # 로드된 모델 목록
curl -X POST http://127.0.0.1:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <LM_STUDIO_TOKEN>" \
  -d '{"model":"google/gemma-4-e4b","messages":[{"role":"user","content":"안녕"}],"max_tokens":4096}'
```

### 12.5 ai_call_logs로 LLM 호출 추적

```bash
sqlite3 backend/ajin.db "SELECT request_id, task_type, status, duration_ms, error_message FROM ai_call_logs ORDER BY created_at DESC LIMIT 10;"
```

상태:
- `success` — 정상
- `api_error` — HTTP 4xx/5xx (rate limit, auth 등)
- `parse_error` — JSON 파싱 실패
- `timeout` — 타임아웃

### 12.6 dependency-free smoke (외부 framework 없음)

```bash
cd backend
python tests/test_smoke_dependency_free.py
```

```bash
cd web-react
node tests/adapters.mjs
```

PR 자동화에 활용. 빠른 회귀 감지.

---

## 13. 개발 컨벤션 + 워크플로

### 13.1 Plan-then-OK 원칙

CLAUDE.md §1.

새 코드/파일 작성/수정 전 사용자에게 "X 하려 합니다" 알리고 yes/ok 동의 후 진행. 단순 조회(git status/grep)는 즉시.

### 13.2 위험 작업 별도 yes

CLAUDE.md §2:
- 파일/폴더 삭제 (`rm`, `Remove-Item`)
- 외부 위치로 `Move-Item`
- `git push`, `git reset --hard`, `git clean -fd`, `--force`
- DB 변경 (`INSERT/DELETE/DROP`, migration 강제)
- 외부 다운로드

### 13.3 추적 파일 수정 전 yes

CLAUDE.md §3. 다음 3종:
- `local/2_work/TODO_polish.md`
- `local/1_PRD/**`
- `local/2_work/reports/**`

### 13.4 절대 건드리지 말 것

CLAUDE.md §4:
- `DraftPage.jsx` / `MyDraftsPage.jsx` / `ArchivePage.jsx` / `SearchPage.jsx` 무단 대체
- `/api/ai/*` 6개 endpoint signature (V1 DraftPage 회귀)
- `drafts` 테이블 스키마
- `PRD/PRD-01.md ~ PRD-12.md` 본문

### 13.5 git 컨벤션

#### 브랜치
```
main                      ← 운영 (보호)
hj                        ← 개인 작업 메인
feat/YYYY-MM-DD-<topic>   ← 단위 작업 (예: feat/2026-05-25-library-hwp-ui)
fix/<topic>               ← 버그 수정
```

#### Commit
```
feat: 기능 추가
fix: 버그 수정
refactor: 구조 개선
docs: 문서
test: 테스트
chore: 기타
```

Co-Authored-By 추가 (AI 협업 시):
```
git commit -m "$(cat <<'EOF'
feat: 기능 설명

상세 내용...

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

#### Push 전 체크
- `.env` 같은 민감 파일 staged X — `git diff --cached` 확인
- 100MB 단일 파일 X — `.gitignore` 통해 차단됨
- 기존 main에 push X — PR 통해

### 13.6 명명 규칙

#### Frontend
- 컴포넌트: PascalCase.jsx
- 훅: useFoo.js
- 유틸: camelCase.js
- API: fooApi 객체

#### Backend
- 라우터: snake_case.py
- 서비스: snake_case.py
- 모델 클래스: PascalCase
- 함수: snake_case
- 환경변수: UPPER_SNAKE_CASE

### 13.7 작업 흐름

#### 큰 작업 (3시간+)
1. **시작:** `local/1_PRD/features/{기능}/{기능}_v01_prd.md` + `*_prompt.md` 생성
2. **STATUS:** "진행 중: {기능}" 갱신
3. **진행 중:** PRD 본문 직접 수정. STATUS 갱신 X.
4. **종료:** `local/2_work/reports/{날짜}_{기능}_report.md` 작성
5. **prompt 정리:** `rm local/1_PRD/features/{기능}/*_prompt.md`
6. **퇴근 루틴:** TODO 체크 → STATUS 덮어쓰기 → git commit

#### 작은 작업 (1시간 이하)
1. 코드만 수정
2. 퇴근 시 한꺼번에: TODO + STATUS + commit
3. PRD/prompt/report 안 만듦

### 13.8 새 대화 시작 시 필수 첨부

```
1. local/2_work/STATUS.md          ← 이걸 먼저 보면 99% 따라잡힘
2. local/2_work/TODO_polish.md
3. local/1_PRD/v0.2/PRD_v0.2_FINAL.md
4. (코드 작업 시) backend/routers/analysis.py, web-react/src/features/pages/draft-v2/DraftPageV2.jsx
```

### 13.9 backend 재시작 시 주의

- `--reload` 옵션 X (Windows watchfiles 충돌)
- Code 변경 후 `Ctrl+C` → 재실행
- backup이 backups/ 에 자동 저장됨 (마이그레이션 시)

### 13.10 frontend Vite 좀비 정리

```powershell
netstat -ano | findstr LISTENING | findstr ":517"
Stop-Process -Id <PID> -Force
```

### 13.11 PR 생성 가이드

```bash
gh pr create \
  --title "feat: <변경 요약>" \
  --body "## Summary
- 변경 1
- 변경 2

## Test plan
- [ ] 백엔드 pytest 통과
- [ ] 프론트엔드 build 성공
- [ ] 브라우저 검증 (Step1 → Step5)

🤖 Generated with Claude Code"
```

---

## 14. 트러블슈팅

### 14.1 백엔드

#### `No module named 'uvicorn'`
**원인**: Conda 환경 활성화됨 (`llm_api` / `bizai`)
**해결**: `conda deactivate` 후 system Python 사용
```powershell
C:\Users\<USER>\AppData\Local\Programs\Python\Python313\python.exe -m uvicorn main:app --port 8000
```

#### `No module named 'dotenv'` / `'sqlalchemy'`
**원인**: 같은 이유. Conda 환경에 패키지 없음
**해결**: system Python 또는
```powershell
pip install -r backend/requirements.txt
```

#### `Address already in use (port 8000)`
**원인**: 이전 backend 좀비
**해결**:
```powershell
netstat -ano | findstr :8000 | findstr LISTENING
Stop-Process -Id <PID> -Force
```

#### `OpenAI 429 — Request too large`
**원인**: gpt-4o TPM 30K 한도 초과 (큰 PDF parse-form 등)
**해결**:
- `parser_mode='hybrid'` (이미 기본값)
- `OPENAI_MODEL_FORM_PARSER=gpt-4o-mini` (TPM 200K)
- `layout_text_safety_cap` 하향

#### `Pydantic schema validation 실패: table_cell_hints`
**원인**: gpt-4o가 `Dict[str, Dict]` 반환, 기존 schema는 `Dict[str, str]`
**해결**: 이미 2026-05-25 `Dict[str, Any]` 로 완화됨. backend 재시작.

#### `Step 2 확정 실패: confirmed_form_schema가 없음`
**원인**: parse-form이 schema validation/TPM으로 실패 → DB 저장 안 됨
**해결**: ai_call_logs 확인:
```bash
sqlite3 backend/ajin.db "SELECT request_id, status, error_message FROM ai_call_logs ORDER BY created_at DESC LIMIT 5;"
```

#### `parse-notice` 응답 없이 timeout
**원인**: OpenAI 응답 지연 (큰 입력) 또는 네트워크
**해결**: 30~60초 대기. ai_call_logs에 duration_ms 확인.

### 14.2 프론트엔드

#### `analysisApi.listSessions is not a function`
**원인**: `backendApi.js` 객체 닫는 `}` 위치 잘못
**해결**: line 190 ~ 508 (analysisApi)이 정상적으로 닫혔는지 확인. 일찍 `}` 닫혀있으면 그 뒤 메서드들이 다른 객체로 들어감.

#### 화면이 안 보임 (whitescreen)
**해결**:
1. F12 → Console 탭 에러 확인
2. 보통 `is not a function` 또는 `Cannot read property of undefined`
3. 해당 파일 import / 함수 시그니처 확인

#### Vite HMR 미반영
**원인**: vite.config.js 변경은 HMR 대상 아님
**해결**: Vite 재시작
```powershell
Stop-Process -Id <vite_PID> -Force
cd web-react; npm run dev
```

#### sessionStorage 캐시로 옛 데이터 표시
**해결**: F12 → Application → Storage → Clear site data → F5

#### `LM Studio 오류 (HTTP 401)`
**원인**: Vite proxy가 토큰 헤더 안 붙임
**해결**: `web-react/.env.server`에 `LM_STUDIO_TOKEN=sk-lm-...` 설정 + Vite 재시작. `vite.config.js`가 자동 주입.

#### `LM Studio가 빈 응답을 반환했습니다 (finish_reason: length)`
**원인**: gemma-4-e4b reasoning 모델 — max_tokens 부족
**해결**:
- 호출처에서 `maxTokens` 2048+ 설정
- 또는 모델을 `qwen2.5-7b-instruct` (비-reasoning)로 변경
- 또는 LM Studio에서 reasoning mode 비활성화 (모델별 다름)

#### `Request URL is missing an 'http://' or 'https://' protocol`
**원인**: backend prefetch에 Vite proxy 경로 (`/proxy/bizfiles/...`) 전달됨
**해결**: frontend에서 `attachment.originalUrl` (절대 URL) 사용. backend도 protocol 가드 추가 (422 명확 에러).

#### Search 페이지에 "백엔드 연결 실패" 토스트
**원인**: backend 안 띄워짐
**해결**: 새 터미널에서 `cd backend; python -m uvicorn main:app --port 8000 --host 127.0.0.1`

### 14.3 자료실 / HWP

#### `HWP 추출 실패: 유효한 HWP/OLE 파일이 아닙니다`
**원인**: 파일이 HWPX 형식 (XML zip)이거나 손상
**해결**: 현재 `hwp_reader.py`는 HWP(OLE 컨테이너)만 지원. HWPX는 별도 처리 필요. 변환 후 업로드.

#### HWP 추출 결과가 깨진 한글
**원인**: 컨트롤 코드 처리 미완 또는 인코딩 이슈
**해결**: `hwp_reader.py:decode_para_text` 의 CTRL_SKIP 보강 필요. 또는 한글 워드 → PDF 변환 후 업로드 권장.

#### 자료실 업로드 timeout (큰 파일)
**원인**: parse_upload_bytes의 PDF/HWP 처리 시간
**해결**: 50MB 이하 권장. 큰 PDF는 페이지 split 후 업로드.

### 14.4 git / 배포

#### 푸시 거부 (large file)
**원인**: 100MB 초과 파일이 commit에 포함됨
**해결**:
1. `.gitignore` 확인
2. `git rm --cached <대용량파일>` 후 재commit
3. `git filter-repo` 또는 BFG로 히스토리 정리 (마지막 수단)

#### `.env` 가 commit됨
**해결**: 즉시 다음 처리:
```bash
git rm --cached backend/.env
git commit -m "chore: remove .env from tracking"
# 그리고 GitHub repo에서 secrets 강제 회전 (API key 새 발급)
```

#### 빌드 에러 (web-react)
```powershell
cd web-react
rm -rf node_modules dist
npm install
npm run build
```

---

## 15. 자주 묻는 질문 (FAQ)

### Q1. 처음 받았는데 어디부터 봐야 하나요?

1. 이 README의 §2 (Quick Start) 따라 백엔드+프론트엔드 띄우기
2. 브라우저에서 한 번 데모 흐름 (Step1 → Step5) 돌려보기
3. `local/2_work/STATUS.md` 읽기 — 현재 진행 상태
4. `local/1_PRD/v0.2/PRD_v0.2_FINAL.md` 읽기 — 전체 기획
5. 이 README §5 (백엔드) / §6 (프론트엔드) — 모듈별 책임

### Q2. 어떤 모델이 어디 쓰이나요?

[§11.2](#112-llm-provider-별-사용처) 참조. 요약:
- 분석/매핑: gpt-4o-mini
- 폼 분석/초안/평가: gpt-4o
- DetailPage AI 분류: LM Studio gemma (로컬, 무료)

### Q3. DB 깨끗하게 초기화하려면?

```powershell
# 백업 후 삭제
copy backend\ajin.db backend\ajin.db.bak.<날짜>
del backend\ajin.db
# backend 재시작하면 Base.metadata.create_all()로 자동 재생성
```

> ChromaDB 도 같이:
> ```powershell
> rmdir /s /q backend\chroma_data
> ```

### Q4. 새 LLM 모델 추가하려면?

1. `backend/services/ai_provider.py` 의 `AIProvider` abstract에 메서드 정의
2. `backend/services/openai_provider.py` (또는 anthropic/local) 에 구현
3. `backend/prompts/{task}.md` 시스템 프롬프트 추가
4. `backend/tests/fixtures/llm_responses/{task}_v1.json` fixture 추가
5. `backend/.env` 에 모델 ID 환경변수 추가

### Q5. 새 페이지 추가하려면?

1. `web-react/src/features/pages/MyNewPage.jsx` 생성
2. `App.jsx` 에 `<Route path="/mynew" element={<MyNewPage />} />` 추가
3. `TopNav.jsx` (필요 시) navItems에 추가
4. backend endpoint 필요하면 `backend/routers/` 에 새 router 작성 + `main.py` 등록

### Q6. 자료실 PDF 추출이 안 돼요

확인 사항:
1. backend `/api/library/files` POST 응답의 `parse_success` 필드
2. `warning` 필드에 에러 메시지
3. 가장 흔한 원인: 스캔 PDF (이미지) — OCR 미구현. 텍스트 PDF만 지원.

### Q7. 마감 지난 공고가 다시 보이게 하려면?

`web-react/src/api/noticesApi.js`의 `dropExpired()` 함수를 우회하거나 옵션 추가. 단 2026-05-25 사용자 결정으로 "무조건 제외" — 토글 없음.

### Q8. v1 (`/draft`) 와 v2 (`/draft-v2`) 차이는?

[§7.10](#710-v1-vs-v2-정책) 참조. v1은 legacy, v2가 신규 표준. v1 보호 (CLAUDE.md §4) — 무단 변경 X.

### Q9. 새 commit 메시지에 Claude 표기 빼고 싶어요

`Co-Authored-By` 라인을 commit 메시지에서 제거하면 됨. AI 협업 명시 정책 (사용자 자율).

### Q10. 팀원이 Mac Mini의 LM Studio를 공유해서 쓰려면?

1. Mac Mini LM Studio → Server 탭 → "Serve on Local Network" ON
2. Mac Mini System Preferences → Network → LAN IP 확인 (예: 192.168.0.10)
3. 팀원 PC의 `web-react/.env.server`:
   ```ini
   LM_STUDIO_URL=http://192.168.0.10:1234
   LM_STUDIO_TOKEN=<Mac Mini에서 발급한 토큰>
   ```
4. 팀원 vite 재시작 (vite.config.js가 dotenv로 .env.server 읽고 proxy 헤더 자동 주입)

### Q11. 백엔드 로그를 파일로 남기려면?

```powershell
cd backend
python -m uvicorn main:app --port 8000 --host 127.0.0.1 --log-level info > backend_8000.log 2>&1
```

> `backend_*.log` 는 `.gitignore` 됨.

### Q12. 비용 알림은 어떻게?

OpenAI Platform → Settings → Limits → "Set monthly budget" + email alert.
Anthropic Console → Settings → Spending limits.

코드 측 안전망: `services/ai_cost.py` 가 `ai_call_logs.cost_estimate_krw` 누적. (관리자 dashboard 미구현 — v0.3)

### Q13. 환경변수 변경 후 안 적용

- backend `.env` 변경 → backend 재시작 필수 (HMR 없음)
- frontend `.env` 변경 → Vite 재시작 (자동 reload 안 됨)
- frontend `.env.local` 도 동일

### Q14. 자료실 카테고리 추가하려면?

`backend/routers/library.py` 의 `LIBRARY_CATEGORIES` set + frontend `MaterialsLibraryPage.jsx` 의 `CATEGORIES` / `UPLOAD_CATEGORIES` 배열 동기화.

### Q15. PR 자동 리뷰 시키려면?

```bash
gh pr create ...   # PR 생성
# 또는 사용자가 별도로 /ultrareview 명령
```

---

## 16. 참고 자료

### 16.1 PRD / 기획

- `PRD/PRD-01_overview.md` ~ `PRD-12_constraints.md` — 공식 PRD (commited, 본문 불변)
- `PRD/PRD-13_change_log.md` — 변경 이력 (수정 가능)
- `local/1_PRD/v0.2/PRD_v0.2_FINAL.md` — ★ 활성 PRD
- `local/1_PRD/v3.2/00_INDEX.md` — v3.2 워크오더 인덱스
- `local/2_work/STATUS.md` — 현재 상태
- `local/2_work/TODO_polish.md` — 부채 누적

### 16.2 외부 링크

- [GitHub Repository](https://github.com/studentjung99/AJIN_PROJECT)
- [프로젝트 공용 드라이브](https://drive.google.com/drive/folders/1Y0CEjy136ItmnRNKZLsx7rGIuncA8MmtfZqSMkPx7mEZg16hrY5mvhNKn1mk0n-Q4kohJo7Q)
- [프로젝트 노션](https://www.notion.so/38637ef64c5382d7aadf016d2dd583cb)

### 16.3 API 문서

- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Anthropic API Reference](https://docs.anthropic.com/en/api)
- [LM Studio Docs](https://lmstudio.ai/docs)
- [공공데이터포털](https://www.data.go.kr/)
- [기업마당 API](https://www.bizinfo.go.kr/web/lay1/program/S1T122C128/openapi/openApiInfo.do)

### 16.4 기술 문서

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
- [Pydantic v2](https://docs.pydantic.dev/latest/)
- [React 18](https://react.dev/)
- [Vite](https://vitejs.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [shadcn/ui](https://ui.shadcn.com/)
- [react-router](https://reactrouter.com/)
- [pdfplumber](https://github.com/jsvine/pdfplumber)
- [pypdfium2](https://github.com/pypdfium2-team/pypdfium2)
- [olefile](https://github.com/decalage2/olefile/wiki)
- [ChromaDB](https://docs.trychroma.com/)

### 16.5 HWP 파일 구조 참고

- [한글 문서 파일 형식 5.0 (한컴)](https://www.hancom.com/cs_center/csDownload.do) — 공식 명세
- 본 프로젝트의 `hwp_reader.py` 는 PARA_TEXT 레코드(태그 0x43) 만 추출 — 표/이미지/스타일 미지원

### 16.6 PRD 13장 인덱스 (간단)

- PRD-01 — 프로젝트 개요
- PRD-02 — 사용자
- PRD-03 — 사용 사례
- PRD-04 — 기능 목록
- PRD-05 — 화면 구조
- PRD-06 — 페이지 구현
- PRD-07 — UI 컴포넌트
- PRD-08 — 데이터 모델
- PRD-09 — API
- PRD-10 — AI 흐름
- PRD-11 — 보안/성능
- PRD-12 — 제약 사항
- PRD-13 — 변경 이력 (수정 가능)

---

## 17. 변경 이력 (이 README)

| 날짜 | 변경 |
|------|------|
| 2026-05-25 | 전면 재작성 — Streamlit 기반 → React + FastAPI 기반 + 자료실/HWP/AI 본문 분석 |

---

## 18. 라이선스

MIT License. `LICENSE` 파일 참조.

---

## 19. 기여 가이드

### 19.1 새 팀원 온보딩 체크리스트

- [ ] 저장소 clone
- [ ] Python 3.13 (system) 설치 확인
- [ ] Node.js 18+ 설치 확인
- [ ] `backend/.env` 생성 + OPENAI_API_KEY 발급
- [ ] `web-react/.env` 생성
- [ ] `pip install -r backend/requirements.txt`
- [ ] `cd web-react && npm install`
- [ ] backend 띄우기 → `/api/health` 확인
- [ ] frontend 띄우기 → 대시보드 확인
- [ ] 데모 흐름 (Step1 → Step5) 한 번 돌려보기
- [ ] `local/2_work/STATUS.md` 읽기
- [ ] CLAUDE.md 운영 지침 숙지

### 19.2 PR 흐름

1. 새 브랜치: `feat/YYYY-MM-DD-<topic>`
2. 작업 (단위 commit)
3. 테스트 (pytest + vitest + 브라우저 확인)
4. push (`git push -u origin <branch>`)
5. PR 생성 (`gh pr create`)
6. 리뷰 → 머지

### 19.3 코드 스타일

- Python: PEP 8 + type hints
- JS/JSX: ESLint (web-react/eslint.config.js)
- 한글 주석 OK (UTF-8)
- 함수/변수명 영어

---

## 20. 연락처 / 지원

- **저장소 owner**: studentjung99
- **현재 작업자**: hjk-meta
- **이슈 트래커**: GitHub Issues
- **문의**: GitHub Discussions 또는 Notion

---

## 21. 부록 A — 모든 API endpoint 한 줄 요약

### 21.1 /api/health
- `GET /api/health` — 헬스체크

### 21.2 /api/notices/*
- `GET /api/notices/search?q=&refresh=` — 검색
- `GET /api/notices` — 목록
- `GET /api/notices/{id}` — 단일
- `POST /api/notices/bulk` — bulk upsert
- `DELETE /api/notices/{id}` — 삭제
- `POST /api/notices/extract-structured` — LLM 분류

### 21.3 /api/analysis/*
- `POST /api/analysis/sessions` — 세션 생성
- `GET /api/analysis/sessions` — 세션 목록
- `GET /api/analysis/sessions/{id}` — 세션 조회
- `DELETE /api/analysis/sessions/{id}` — soft delete
- `GET /api/analysis/sessions/{id}/step3-ready` — Step3 진입 게이트
- `GET /api/analysis/sessions/{id}/mapping-status` — mapping 진행 상태
- `POST /api/analysis/files` — multipart 업로드
- `GET /api/analysis/files` — 세션 첨부 목록
- `POST /api/analysis/parse-notice`
- `POST /api/analysis/parse-form`
- `POST /api/analysis/extract-evidence`
- `POST /api/analysis/analyze-company`
- `POST /api/analysis/missing-materials`
- `POST /api/analysis/write-draft-item`
- `POST /api/analysis/write-all-drafts`
- `POST /api/analysis/evaluate-draft`
- `POST /api/analysis/export-docx`
- `POST /api/analysis/confirm-step2`
- `PATCH /api/analysis/form-schema/section`
- `PATCH /api/analysis/form-schema/question`
- `GET /api/analysis/eval-criteria-mappings`
- `PATCH /api/analysis/eval-criteria-mappings/{id}`
- `GET /api/analysis/eval-criteria-mappings/{id}/history`
- `POST /api/analysis/mapping` — BackgroundTasks
- `PATCH /api/analysis/sessions/{id}/drafts-policy`
- `POST /api/analysis/reanalyze`

### 21.4 /api/files/*
- `POST /api/parse-file` — 단일 파일 텍스트 추출
- `POST /api/parse-files` — 다중
- `POST /api/files/prefetch-url` — URL 다운로드 + parse
- `POST /api/files/export-hwpx` — text/lines → HWPX

### 21.5 /api/library/*
- `POST /api/library/files` — 업로드 (카테고리)
- `GET /api/library/files?category=&sort=` — 리스트
- `GET /api/library/files/{id}` — 상세
- `DELETE /api/library/files/{id}` — soft delete

### 21.6 /api/company/*
- `POST /api/company/files` — 업로드
- `GET /api/company/files` — 목록
- `GET /api/company/files/{id}` — 단일
- `DELETE /api/company/files/{id}` — 삭제

### 21.7 /api/drafts/*
- `GET /api/drafts` — V1 목록
- `POST /api/drafts` — V1 생성
- `GET /api/drafts/{id}`
- `PATCH /api/drafts/{id}`
- `DELETE /api/drafts/{id}`

### 21.8 /api/bookmarks/*
- `GET /api/bookmarks`
- `POST /api/bookmarks`
- `DELETE /api/bookmarks/{notice_id}`

### 21.9 /api/profile/*
- `GET /api/profile` — V1 프로필
- `PUT /api/profile`

### 21.10 /api/chat/*
- `POST /api/chat/draft-assist` — Step3 보완 대화

### 21.11 /api/ai/* (V1, deprecated)
- 변경 금지 (CLAUDE.md §4)

---

## 22. 부록 B — 환경 검증 스크립트

처음 받은 환경이 정상 동작하는지 한 번에 확인:

```powershell
# 1. Python 버전 확인
python --version
# Expected: Python 3.13.x

# 2. Python 패키지
python -c "import fastapi, uvicorn, sqlalchemy, openai, pdfplumber, olefile; print('OK')"
# Expected: OK

# 3. Node.js
node --version
# Expected: v18.x.x 이상

# 4. npm 패키지
cd web-react
npm list react vite tailwindcss
# Expected: 버전 표시

# 5. .env 파일 존재
test -f backend/.env && echo "backend/.env OK" || echo "MISSING"
test -f web-react/.env && echo "web-react/.env OK" || echo "MISSING"

# 6. backend 가동
cd backend
python -m uvicorn main:app --port 8000 --host 127.0.0.1 &
sleep 5
curl http://127.0.0.1:8000/api/health
# Expected: {"status":"ok",...}

# 7. frontend 가동
cd web-react
npm run dev &
sleep 10
curl -o /dev/null -w "%{http_code}" http://localhost:5173/
# Expected: 200
```

---

## 23. 부록 C — 키보드 단축키 (브라우저)

| 단축키 | 동작 |
|--------|------|
| `Ctrl+R` / `F5` | 새로고침 |
| `Ctrl+Shift+R` | 캐시 무시 새로고침 |
| `F12` | 개발자 도구 |
| `Ctrl+Shift+I` | 동일 |
| `Ctrl+Shift+J` | 콘솔 직접 |
| `Ctrl+Shift+C` | 요소 inspector |
| `Ctrl+Shift+Delete` | 인터넷 사용 기록 삭제 |

VSCode 단축키 (참고):
| 단축키 | 동작 |
|--------|------|
| `Ctrl+Shift+P` | Command Palette |
| `Ctrl+P` | 파일 quick open |
| `Ctrl+Shift+F` | 전체 검색 |
| `Ctrl+B` | 사이드바 토글 |
| `` Ctrl+` `` | 터미널 토글 |

---

## 24. 부록 D — 자주 쓰는 grep 패턴

```bash
# 백엔드: 특정 endpoint 찾기
grep -n "@router\." backend/routers/analysis.py | head -30

# 백엔드: import 모음
grep -h "^import\|^from " backend/routers/*.py backend/services/*.py | sort -u

# 프론트엔드: 한글 UI 텍스트 위치
grep -rn "신규 작성\|초안 이어 작성" web-react/src --include="*.jsx"

# 환경변수 사용처
grep -rn "process\.env\|import\.meta\.env" backend web-react/src --include="*.py" --include="*.js" --include="*.jsx"

# TODO 마커
grep -rn "TODO\|FIXME\|XXX\|HACK" backend web-react/src --include="*.py" --include="*.jsx" --include="*.js"
```

---

## 25. 마치며

이 README는 한 번에 다 읽지 않으셔도 됩니다. 다음 순서로 보세요:

1. **새 팀원**: §1 (소개) → §2 (Quick Start) → §15 (FAQ)
2. **백엔드 작업**: §5 (백엔드 상세) → §9 (환경변수) → §10 (DB) → §14.1 (트러블슈팅)
3. **프론트엔드 작업**: §6 (프론트엔드 상세) → §7 (초안 작성 흐름) → §14.2 (트러블슈팅)
4. **자료실/AI 작업**: §8 → §11 (LLM 통합)
5. **PR 작성 시**: §13 (컨벤션)
6. **장애 대응**: §14 (트러블슈팅)

질문이나 개선 제안은 GitHub Issues 또는 PR로 환영합니다.

**Happy coding! 🚀**

---

## 26. DB 연결 + ERD 상세 가이드

### 26.1 SQLite 연결 구조

#### `backend/database.py`

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ajin.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite + FastAPI 동시 접근
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

#### Dependency Injection

각 router endpoint에서:

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from database import get_db

@router.get("/something")
def something(db: Session = Depends(get_db)):
    return db.query(Model).all()
```

`get_db()` 가 yield로 session 반환 → endpoint 종료 시 자동 close. 트랜잭션은 endpoint 내에서 `db.commit()` 또는 `db.rollback()` 명시.

#### 자동 테이블 생성

`backend/main.py`:
```python
Base.metadata.create_all(bind=engine)
```

→ `models.py`에 선언된 모든 ORM 클래스의 테이블이 없으면 생성. 있으면 그대로 (스키마 ALTER 안 함).

스키마 변경 시 `migrations/00NN_*.py` 별도 작성 + 수동 실행 (Alembic 아님).

### 26.2 ERD (Entity Relationship Diagram)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  V1 Legacy (CLAUDE.md §4 보호 — 수정 금지)                                 │
│                                                                            │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐            │
│  │ notices  │    │  drafts  │    │bookmarks │    │ profile  │            │
│  └──────────┘    └────┬─────┘    └──────────┘    └──────────┘            │
│                       │                                                    │
│                       └─ parent_draft_id (self-ref, 버전 관리)            │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  Audit                                                                     │
│                                                                            │
│  ┌──────────────┐                                                          │
│  │ai_call_logs  │  ← 모든 LLM 호출 추적 (request_id / task_type / status   │
│  │              │     / duration_ms / token_usage_json / cost_estimate_krw)│
│  └──────────────┘                                                          │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  V0.2 Ontology (PRD §13.1)                                                 │
│                                                                            │
│              ┌────────────────────────────┐                                │
│              │  application_sessions      │  ← 모든 산출물의 부모          │
│              │                            │                                │
│              │  session_id (PK)           │                                │
│              │  user_id                   │                                │
│              │  company_profile_id        │                                │
│              │  notice_file_id ───────────┼──┐ soft (no FK)                │
│              │  form_file_id ─────────────┼──┤   → schema_json.attachments │
│              │  reference_file_ids[] ─────┼──┘                             │
│              │  selected_company_file_ids[]─────┐ soft → company_files     │
│              │                            │     │                          │
│              │  status / current_step     │     │                          │
│              │  notice_schema_json (JSON) │     │                          │
│              │  form_schema_json (JSON)   │     │                          │
│              │  company_schema_json (JSON)│     │                          │
│              └─────────┬──────────────────┘     │                          │
│                        │ 1:N (FK session_id)    │                          │
│           ┌────────────┼────────────┬──────────────┬──────────┐          │
│           ▼            ▼            ▼              ▼          ▼          │
│  ┌────────────┐ ┌─────────────┐ ┌──────────────┐ ┌──────────┐ ┌────────┐│
│  │evidence_   │ │mapping_     │ │missing_      │ │fit_      │ │draft_  ││
│  │items       │ │results      │ │materials     │ │analyses  │ │items   ││
│  │            │ │             │ │              │ │(1:1)     │ │        ││
│  │evidence_id │ │id (auto)    │ │missing_id    │ │id        │ │draft_id││
│  │session_id  │ │session_id   │ │session_id    │ │session_id│ │session_││
│  │source_file │ │question_id  │ │question_id   │ │company_  │ │  id    ││
│  │type        │ │matched_evi_ │ │missing_type  │ │profile_id│ │question││
│  │content     │ │  ids[]      │ │name          │ │axes_json │ │  _id   ││
│  │raw_text    │ │used_evi_    │ │description   │ │overall_  │ │content ││
│  │matched_    │ │  ids[]      │ │input_type    │ │  score   │ │table_  ││
│  │  questions[]│ │confidence_  │ │status        │ └──────────┘ │  data  ││
│  │confidence_ │ │  score      │ │supplemental_ │              │used_   ││
│  │  per_      │ │missing_evi_ │ │  ids[]       │              │  evi_  ││
│  │  question{}│ │  types[]    │ │resolved_at   │              │  ids[] ││
│  │embedding_  │ │match_status │ └──────┬───────┘              │status  ││
│  │  blob      │ └─────────────┘        │ 1:N                  │warnings││
│  └────────────┘                        │ (missing_id)         │        ││
│                                        ▼                      └────────┘│
│                              ┌─────────────────┐                         │
│                              │supplemental_    │                         │
│                              │materials        │                         │
│                              │                 │                         │
│                              │supplemental_id  │                         │
│                              │session_id       │                         │
│                              │question_id      │                         │
│                              │missing_id (FK)  │                         │
│                              │type             │                         │
│                              │content          │                         │
│                              │file_id          │                         │
│                              │evidence_ids[]   │                         │
│                              └─────────────────┘                         │
│                                                                            │
│              ┌────────────────────────────┐                                │
│              │eval_criteria_mappings      │                                │
│              │                            │                                │
│              │criteria_id (PK)            │                                │
│              │session_id (FK)             │                                │
│              │criteria_name               │                                │
│              │weight                      │                                │
│              │scope (section/question/    │                                │
│              │       general)             │                                │
│              │mapped_questions[]          │                                │
│              │mapping_type (direct/...)   │                                │
│              │mapped_by (ai/user)         │                                │
│              │confidence                  │                                │
│              │reason                      │                                │
│              │source_page                 │                                │
│              │history (JSON 누적)         │  ← migration 0005            │
│              └────────────────────────────┘                                │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  운영 보조 (PRD §13.10)                                                    │
│                                                                            │
│  ┌────────────────────────────────┐                                        │
│  │company_files                    │  ← 기업프로필 자료 + 자료실 통합     │
│  │                                 │     (2026-05-25 file_type enum 확장) │
│  │file_id (PK)                     │                                        │
│  │company_profile_id (인덱스)      │                                        │
│  │file_name                        │                                        │
│  │file_storage_path                │  ← 디스크 BLOB 경로                   │
│  │file_type (회사자료/첨부자료/    │                                        │
│  │           필요자료 또는 legacy) │                                        │
│  │parsed_text (≤200K) ★            │  ← 자동 텍스트 추출 (migration 0004) │
│  │char_count / truncated /         │                                        │
│  │parse_success / warning          │                                        │
│  │uploaded_at / updated_at         │                                        │
│  │status (active/deleted)          │                                        │
│  │tags (JSON)                      │                                        │
│  └────────────────────────────────┘                                        │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  외부 Vector Store (별도 시스템)                                            │
│                                                                            │
│  ┌────────────────────────────────┐                                        │
│  │ChromaDB (backend/chroma_data/)  │                                        │
│  │                                 │                                        │
│  │collection: evidence_{session_id}│                                        │
│  │  - id: evidence_id              │                                        │
│  │  - embedding: vector            │                                        │
│  │  - metadata: { type, source }   │                                        │
│  │  - document: content text       │                                        │
│  └────────────────────────────────┘                                        │
│                                                                            │
│  evidence_items.embedding_blob ← soft ref (id 매칭)                       │
└──────────────────────────────────────────────────────────────────────────┘
```

### 26.3 관계 매트릭스

| 부모 | 자식 | 관계 | FK? | cascade |
|------|------|------|------|---------|
| application_sessions | evidence_items | 1:N | ✅ (session_id) | 코드 레벨 |
| application_sessions | mapping_results | 1:N | ✅ | 코드 레벨 |
| application_sessions | missing_materials | 1:N | ✅ | 코드 레벨 |
| application_sessions | supplemental_materials | 1:N | ✅ | 코드 레벨 |
| application_sessions | fit_analyses | 1:1 (UNIQUE) | ✅ | 코드 레벨 |
| application_sessions | eval_criteria_mappings | 1:N | ✅ | 코드 레벨 |
| application_sessions | draft_items | 1:N | ✅ | 코드 레벨 |
| missing_materials | supplemental_materials | 1:N | ✅ (missing_id) | 코드 레벨 |
| application_sessions | company_files | N:M (soft) | ❌ | selected_company_file_ids[] |
| evidence_items | mapping_results.matched_evidence_ids[] | N:M (soft) | ❌ | JSON 배열 |
| evidence_items | draft_items.used_evidence_ids[] | N:M (soft) | ❌ | JSON 배열 |

> **모든 FK는 SQLAlchemy 모델 레벨만 정의 (DB 제약 없음)**. SQLite의 FK 제약은 `PRAGMA foreign_keys=ON` 필요한데 v0.2에선 사용 안 함. 무결성은 코드(`db.query` + 명시적 검사)에서 보장.

### 26.4 JSON 컬럼 상세

#### `notice_schema_json` 구조

```json
{
  "schema": {
    "notice_title": "...",
    "target": "지원 대상...",
    "benefit": "지원 내용...",
    "documents": "제출 서류...",
    "period": "2026-06-01 ~ 2026-07-31",
    "deadline": "2026-07-31",
    "region": "전국",
    "limit": "...",
    "content": "...",
    "evaluation_criteria": [
      { "name": "기술성", "weight": 40, "rubric": "..." },
      { "name": "사업성", "weight": 30, "rubric": "..." }
    ],
    "ai_interpretation": { ... }
  },
  "attachments": [
    {
      "file_id": "f_abc123def456",
      "kind": "notice",
      "file_name": "공고문.pdf",
      "ext": ".pdf",
      "size_bytes": 1234567,
      "char_count": 50000,
      "parsed_text": "(전문 ≤200K)",
      "parsed_text_truncated": false
    }
  ],
  "parser_metadata": {
    "provider": "openai",
    "model": "gpt-4o",
    "parsed_at": "2026-05-25T10:30:00",
    "duration_ms": 12500,
    "tokens_used": 8500
  }
}
```

#### `form_schema_json` 구조

```json
{
  "schema": {
    "form_id": "form_001",
    "form_name": "사업계획서.pdf",
    "sections": [
      {
        "section_id": "S001",
        "title": "1. 사업 개요",
        "order": 1,
        "questions": [
          {
            "question_id": "S001-Q001",
            "title": "사업명",
            "original_text": "...",
            "requirement": "한 줄로 작성",
            "writing_guidelines": ["구체적으로", "30자 이내"],
            "constraints": {
              "max_length": 30, "min_length": 0,
              "format": null, "page_limit": null
            },
            "fill_mode": "ai_text",
            "is_required": true,
            "is_table_item": false,
            "source_page": 1,
            "_parser_hint": { "header_candidate": false }
          },
          {
            "question_id": "S001-T001",
            "title": "사업 일정",
            "is_table_item": true,
            "fill_mode": "table_input",
            "table_columns": ["단계", "기간", "내용"],
            "table_schema": {
              "columns": [
                { "field_id": "col_001", "header_path": ["단계"], "data_type": "text" },
                { "field_id": "col_002", "header_path": ["기간"], "data_type": "date" }
              ],
              "header_cells": [...],  ← Option C: 표 헤더 cell
              "data_rows": [...]      ← Option C: 표 데이터 행
            }
          }
        ]
      }
    ],
    "excluded_question_ids": ["S001-Q005"],
    "quality_metrics": {
      "question_count": 35,
      "table_count": 8,
      "needs_repair": false
    },
    "quality_status": "ok"
  },
  "confirmed_schema": { ... },  ← Step2 confirm-step2 호출 시 snapshot
  "attachments": [ ... ],
  "parser_metadata": { ... }
}
```

#### `company_schema_json` 구조

```json
{
  "schema": {
    "company_name": "...",
    "industry": "자동차 부품",
    "strengths": ["...", "..."],
    "weaknesses": [...],
    "core_competencies": [...],
    "recent_achievements": [...]
  },
  "fit_analysis": { ... },
  "parser_metadata": { ... }
}
```

### 26.5 트랜잭션 패턴

#### 단순 read
```python
@router.get("/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == session_id
    ).first()
    if not session:
        raise HTTPException(404, "not found")
    return _to_dict(session)
```

#### Read + Write (JSON 컬럼)
```python
@router.patch("/form-schema/question")
def patch_question(req, db: Session = Depends(get_db)):
    session = db.query(ApplicationSession).filter(...).first()

    # JSON 컬럼은 dict 복사 후 수정 → flag_modified 호출 필수
    fsj = dict(session.form_schema_json or {})
    schema = dict(fsj.get("schema") or {})
    # ... schema 수정 ...
    fsj["schema"] = schema
    session.form_schema_json = fsj

    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(session, "form_schema_json")  # ★ 필수!

    db.commit()
    return {"saved": True}
```

> **⚠ JSON 컬럼 수정 시 `flag_modified` 호출 안 하면 SQLAlchemy가 변경 감지 못 함** → 저장 안 됨. analysis.py 의 거의 모든 PATCH endpoint에서 사용.

#### BackgroundTasks (mapping pipeline)
```python
@router.post("/mapping")
async def trigger_mapping(req, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # 즉시 응답
    background_tasks.add_task(run_mapping_pipeline, req.session_id)
    return {"status": "started"}

def run_mapping_pipeline(session_id: str):
    # 별도 SessionLocal로 새 트랜잭션 (request scope 분리)
    db = SessionLocal()
    try:
        # ... 시간 걸리는 작업 ...
        db.commit()
    finally:
        db.close()
```

### 26.6 인덱스 전략

migration에서 생성:

```sql
CREATE INDEX ix_application_sessions_user_id     ON application_sessions(user_id);
CREATE INDEX ix_application_sessions_status      ON application_sessions(status);

CREATE INDEX ix_evidence_items_session_id        ON evidence_items(session_id);

CREATE INDEX ix_mapping_results_session_id       ON mapping_results(session_id);
CREATE INDEX ix_mapping_results_question_id      ON mapping_results(question_id);
CREATE INDEX ix_mapping_results_match_status     ON mapping_results(match_status);

CREATE INDEX ix_missing_materials_session_id     ON missing_materials(session_id);
CREATE INDEX ix_missing_materials_question_id    ON missing_materials(question_id);
CREATE INDEX ix_missing_materials_status         ON missing_materials(status);

CREATE INDEX ix_draft_items_session_id           ON draft_items(session_id);
CREATE INDEX ix_draft_items_question_id          ON draft_items(question_id);
CREATE INDEX ix_draft_items_status               ON draft_items(status);

CREATE INDEX ix_ai_call_logs_request_id          ON ai_call_logs(request_id);
CREATE INDEX ix_ai_call_logs_task_type           ON ai_call_logs(task_type);
CREATE INDEX ix_ai_call_logs_status              ON ai_call_logs(status);
CREATE INDEX ix_ai_call_logs_created_at          ON ai_call_logs(created_at);

CREATE INDEX ix_company_files_company_profile_id ON company_files(company_profile_id);
CREATE INDEX ix_company_files_status             ON company_files(status);
```

자주 쓰는 쿼리 (`session_id` 필터)는 항상 인덱스 사용. 신규 쿼리 추가 시 EXPLAIN으로 확인.

### 26.7 SQLite vs Postgres 마이그레이션 계획 (v0.3)

| 항목 | SQLite (v0.2) | Postgres (v0.3 검토) |
|------|--------------|---------------------|
| 동시 쓰기 | 불가 (one-writer) | 가능 (MVCC) |
| JSON 컬럼 | TEXT (검색 느림) | JSONB (인덱스 가능) |
| Vector | 별도 ChromaDB | pgvector 일원화 |
| Storage | 단일 파일 | 서버 |
| 운영 | 백업 = 파일 복사 | pg_dump |

마이그레이션 시 변경 필요:
- `DATABASE_URL=postgresql://user:pwd@host:5432/db`
- SQLAlchemy DDL은 거의 그대로
- JSON 컬럼 → JSONB 캐스팅 (SELECT 시 `::jsonb`)
- ChromaDB → pgvector (별도 작업)

### 26.8 백업 / 복구

#### 자동 백업
마이그레이션 실행 시 `backend/backups/ajin_NNNN_pre_YYYYMMDD_HHMMSS.db` 생성.

#### 수동 백업
```powershell
copy backend\ajin.db backend\backups\ajin_manual_$(Get-Date -Format yyyyMMdd).db
```

#### 복구
```powershell
# 백엔드 중지
Stop-Process -Id <PID> -Force
# 백업 복사
copy backend\backups\ajin_0005_pre_*.db backend\ajin.db
# 백엔드 재시작
cd backend; python -m uvicorn main:app --port 8000 --host 127.0.0.1
```

### 26.9 DB 직접 조회 (디버깅)

```bash
# 세션 목록
sqlite3 backend/ajin.db "SELECT session_id, status, current_step, updated_at FROM application_sessions ORDER BY updated_at DESC LIMIT 10;"

# 특정 세션의 form_schema 일부
sqlite3 backend/ajin.db "SELECT json_extract(form_schema_json, '$.schema.quality_status') FROM application_sessions WHERE session_id='...';"

# 최근 LLM 호출
sqlite3 backend/ajin.db "SELECT request_id, task_type, status, duration_ms, error_message FROM ai_call_logs ORDER BY created_at DESC LIMIT 20;"

# 자료실 파일
sqlite3 backend/ajin.db "SELECT file_id, file_name, file_type, char_count, status FROM company_files WHERE status='active' ORDER BY uploaded_at DESC;"

# 매핑 결과
sqlite3 backend/ajin.db "SELECT question_id, confidence_score, match_status, length(matched_evidence_ids) FROM mapping_results WHERE session_id='...';"
```

### 26.10 ERD 시각화 (Mermaid)

`local/2_work/db/current_database_erd.mmd` — Mermaid 형식 ERD. VS Code Mermaid 확장으로 렌더링 가능.

```mermaid
erDiagram
    application_sessions ||--o{ evidence_items : "1:N"
    application_sessions ||--o{ mapping_results : "1:N"
    application_sessions ||--o{ missing_materials : "1:N"
    application_sessions ||--o{ supplemental_materials : "1:N"
    application_sessions ||--|| fit_analyses : "1:1"
    application_sessions ||--o{ eval_criteria_mappings : "1:N"
    application_sessions ||--o{ draft_items : "1:N"
    missing_materials ||--o{ supplemental_materials : "1:N (missing_id)"
    application_sessions }o--o{ company_files : "N:M soft ref"
```

---

## 27. Step 2 분석 — 성능 고도화 가이드

> Step 2는 사용자가 **가장 오래 기다리는 단계**입니다 (parse-form 30~80초, parse-notice 10~20초, evidence/company 병렬 5~30초). 본 섹션은 측정 가능한 개선 방안 정리.

### 27.1 현재 병목 측정

#### 측정 방법

브라우저 개발자도구 Network 탭에서 다음 4개 호출의 응답 시간:
- POST `/api/analysis/parse-notice`
- POST `/api/analysis/parse-form`
- POST `/api/analysis/extract-evidence`
- POST `/api/analysis/analyze-company`

병렬 실행이므로 가장 느린 호출이 사용자 대기 시간.

#### 표준 측정 케이스 (자동차 부품 38페이지 PDF)

| 호출 | 평균 시간 | 토큰 (input/output) | 비용 |
|------|----------|-------------------|------|
| parse-notice | 10~15초 | 2K / 1K | ~$0.005 |
| parse-form (single) | 30~50초 (성공 시) | 30K / 4K | ~$0.05 |
| parse-form (hybrid) | 60~80초 (chunked) | 30K / 12K | ~$0.08 |
| extract-evidence | 5~30초 (자료 크기) | 5K / 2K | ~$0.01 |
| analyze-company | 5~15초 | 3K / 2K | ~$0.008 |

### 27.2 parse-form 최적화 7가지

#### 27.2.1 Hybrid mode (chunked parallel) — 이미 적용 ✅

큰 PDF를 regex 챕터로 분할 → 병렬 호출 → merger가 ID 재할당.

```python
# backend/services/form_parser_hybrid.py
async def parse_form_hybrid(form_text, form_name, provider, ...):
    chunks = _split_by_chapter(form_text)         # regex: "^N\. " 패턴
    results = await asyncio.gather(*[
        provider.form_parser(chunk, form_name, request_id=f"{req_id}_c{i}")
        for i, chunk in enumerate(chunks)
    ], return_exceptions=True)
    merged = _merge_chunks(results, hybrid_meta)
    return merged
```

**효과**: 1개 호출에 30K 토큰 → 11개 호출에 평균 3K 토큰. 각 호출은 빠름. 단 TPM(분당 토큰) 한도 동시 누적 → 일부 chunk가 429.

**개선 방향**:
- chunk 간 호출 간격 조절 (rate limiter): `await asyncio.sleep(0.5)` 사이 sleep
- 실패한 chunk만 재시도 (exponential backoff)
- chunk별 token 사전 측정 → TPM 한도 이내로 batch 묶기

#### 27.2.2 Layout-aware text cap

전체 PDF text를 LLM에 보내는 대신 layout IR에서 page 단위로 잘라서 보냄.

```python
# backend/services/form_layout_builder.py
form_text, layout_meta, layout_pages = _build_layout_aware_text(items)
# layout_meta: { pages_total, pages_included, layout_text_truncated, ... }
```

**현재 cap**: `FORM_LAYOUT_TEXT_SAFETY_CAP` 환경변수 (default 30K chars).

**개선 방향**:
- 페이지별 token 측정 → 누적 한도 도달 시 자름
- 우선순위 페이지: 표 있는 페이지 > 텍스트 페이지

#### 27.2.3 Pre-classification (LLM 호출 전)

LLM이 모든 페이지를 분석하지 않게 사전 필터.

**아이디어**:
- pdfplumber로 표/체크박스/필드 마커 수 측정
- 표지(첫 1~2 페이지)는 별도 prompt
- 빈 페이지 / 부록 페이지 자동 skip

**예상 효과**: 입력 토큰 30% 감소 → 비용/시간 절감

#### 27.2.4 Table normalizer + Promoter (Option C 적용 ✅)

LLM이 표를 텍스트로만 추출하면 cell 단위 데이터 손실. layout IR에서 cell 그대로 보존:

```python
# backend/services/table_normalizer.py
normalized = normalize_layout_tables(layout_pages)
# normalized[i]: NormalizedTable { header_path, cells_raw, ... }

# backend/services/table_promoter.py
result, stats = promote_tables(normalized, llm_result)
# table_schema.header_cells, data_rows 추가 (Option C)
```

**효과**: LLM이 표를 빠뜨려도 layout-deterministic 자동 보강.

**개선 방향**:
- header_path 추론 정확도 향상 (병합 셀 처리)
- 비-grid 표 (key-value 폼) 자동 인식
- title_candidate 추출 (표 위 제목 줄)

#### 27.2.5 Repair pass (1-pass)

`quality_metrics["needs_repair"] = True` 면 의심 페이지만 다시 LLM 호출:

```python
# backend/routers/analysis.py:parse_form
if quality_metrics["needs_repair"] and suspect_text and not layout_truncated:
    repair_result = await provider.form_parser(suspect_text, form_name, ...)
    result = _merge_repair_schema(result, repair_result)
```

**현재 트리거**:
- question_count < 5 (페이지 수 대비)
- empty_field 누락
- table 누락

**개선 방향**:
- repair 시 max_tokens 2배 (output 보강)
- 누락된 섹션만 타겟 prompt (전체 재호출 방지)
- repair 결과 자동 검증 (변경 X면 quality_status='repair_failed')

#### 27.2.6 Prompt 최적화 (form_parser.md v1.4)

**현재 prompt 핵심**:
- §0 TOC-first rule (목차 우선 검토)
- 다중 양식 처리 (서식 헤더 패턴 + "한 서식은 다음 헤더 직전까지 모든 페이지")
- 3-1/3-2/4-1 sub-번호 별도 문항
- `<EMPTY_FIELD id="...">` / `[ ]` 체크박스 / `<SIGNATURE_FIELD>` 마커

**개선 방향**:
- few-shot examples 추가 (특정 패턴 ex: 한글 표지)
- 표 vs key-value 구분 명시 (현재 false table 13열 오인식 부채)
- table_cell_hints 형식 명시 (`Dict[str, Any]` 허용)

#### 27.2.7 Caching

같은 form_text를 다시 분석하지 않게:

**아이디어**:
- `input_hash = sha256(form_text + parser_mode + model_name)`
- `ai_call_logs.input_hash` 컬럼 (이미 있음) 으로 조회
- hit이면 `output_json` 그대로 반환

**현재 미구현**. 향후 추가 가치 큼 (개발 중 재분석 비용 절감).

### 27.3 parse-notice 최적화

#### 27.3.1 텍스트 압축

공고문은 길지만 형식적 반복 많음. 광고/footnote 제거.

#### 27.3.2 evaluation_criteria 분리 호출

평가기준은 별도 LLM 호출로:
- parse-notice (기본 정보) — gpt-4o-mini, 빠름
- eval_criteria_extractor (평가표) — gpt-4o, 정확

병렬 실행으로 시간 비슷, 비용 효율.

### 27.4 extract-evidence 최적화

#### 27.4.1 chunk 크기 튜닝

현재 512 token 단위. 문장 경계 보존:
```python
# backend/services/evidence_chunker.py
def chunk_text(text, chunk_size=512, overlap=64):
    # sentence boundary aware
    ...
```

**튜닝 가이드**:
- 큰 chunk (1024): 컨텍스트 풍부, 정밀도 ↑, 검색 noise ↑
- 작은 chunk (256): 정확한 매칭, recall ↓
- 권장: 512 + overlap 64

#### 27.4.2 embedding 모델 선택

- `bge-m3-ko` (한국어 특화) — 권장
- `openai-text-embedding-3-large` — 정확도 ↑ 비용 ↑
- `nomic-embed-text-v1.5` (LM Studio 로컬) — 무료

### 27.5 analyze-company 최적화

#### 27.5.1 company 파일 사전 요약

기업 자료(회사소개서/재무제표)가 큰 경우 사전 요약 → analyze-company에 요약본만 전달.

```python
company_summary = await provider.summarize(company_files_text, max_tokens=2000)
result = await provider.company_analyzer(company_summary, notice_schema)
```

**효과**: 입력 토큰 70% 감소, 응답 빠름.

### 27.6 mapping_pipeline 최적화 (Step2 후반)

BackgroundTasks로 비동기 실행 — 사용자 Step2 보는 동안 매핑 진행.

```python
# backend/routers/analysis.py:trigger_mapping
@router.post("/mapping")
async def trigger_mapping(req, background_tasks: BackgroundTasks, db):
    background_tasks.add_task(run_mapping_pipeline, req.session_id)
    return {"status": "started"}
```

frontend `getMappingStatus` 로 polling:
```js
const status = await analysisApi.getMappingStatus(sessionId)
// { done: 15, total: 35, status: 'in_progress' }
```

**개선 방향**:
- progress event (WebSocket / SSE) — 실시간 progress bar
- 부분 결과 표시 (완료된 문항부터 Step3 활성화)

### 27.7 frontend 최적화

#### 27.7.1 sessionStorage 캐시

`writeStep2Cache(sessionId, { formApiResp, formData })` — sessionStorage에 저장 → 새로고침 시 즉시 복원 (backend 호출 없이).

#### 27.7.2 병렬 호출

```js
Promise.allSettled([
  analysisApi.parseForm(...),
  analysisApi.extractEvidence(...),
  analysisApi.analyzeCompany(...),
])
```

4개 호출이 직렬이 아닌 병렬 → 총 시간 = max(개별 시간).

#### 27.7.3 Tab 분리

Tab1(공고문) + Tab2(제출양식). 사용자는 한 번에 하나만 봄. 다른 Tab의 무거운 컴포넌트는 lazy load:

```jsx
const Tab2FormPreview = lazy(() => import('./Tab2FormPreview'))
```

#### 27.7.4 PDF 미리보기 lazy

react-pdf 의 `<Document>` 는 무거움. 사용자가 PDF 영역 펼칠 때만 로드.

### 27.8 quality_metrics + Diagnostic UI

Step2 footer에 Quality Diagnostic 표시:
- question_count / table_count / promoted_table_count
- needs_repair / repaired / quality_status

`web-react/src/lib/step2QualityDiagnostic.js` — 11 metric + 8 위험 신호.

사용자가 직접 보고 "재분석" 결정.

### 27.9 Step2 측정 + 개선 우선순위

| 우선순위 | 항목 | 예상 효과 | 난이도 |
|---------|------|----------|--------|
| 1 | Hybrid mode chunk rate limiter | TPM 429 → 0 | 작음 |
| 2 | parse-form input caching | 재분석 비용 90%↓ | 중간 |
| 3 | Layout pre-classification | 토큰 30%↓ | 중간 |
| 4 | mapping_pipeline progress SSE | UX ↑ | 중간 |
| 5 | repair pass 타겟 prompt | 정확도 ↑ | 큼 |
| 6 | Postgres + JSONB | 동시 사용자 지원 | 큼 |

---

## 28. Step 3 초안 작성 — 성능 고도화 가이드

> Step 3는 **문항 N개 × 초안 1개 ≈ N회 LLM 호출**. 문항이 35개면 35분 (각 1분). 사용자 대기 시간 + 비용 둘 다 큼.

### 28.1 현재 흐름 측정

| 단위 | 평균 시간 | 토큰 |
|------|----------|------|
| `write-draft-item` (단일 문항) | 30~60초 | 입력 3~5K / 출력 1~2K |
| `write-all-drafts` (35 문항 직렬) | 20~30분 | 누적 100K+ |
| 표 항목 (table_input) | 5~10초 | 1K / 0.5K |

### 28.2 write-draft-item 최적화 8가지

#### 28.2.1 Evidence 기반 우선 (mapping_result 활용)

문항별로 사전 매핑된 evidence_ids만 prompt에 넣음:

```python
# backend/services/draft_writer 흐름
mapping = db.query(MappingResult).filter(
    MappingResult.session_id == sid, MappingResult.question_id == qid
).first()

evidences = db.query(EvidenceItem).filter(
    EvidenceItem.evidence_id.in_(mapping.matched_evidence_ids)
).all()

prompt = build_draft_prompt(question, evidences, company_schema)
result = await provider.draft_writer(prompt, ...)
```

**효과**: 모든 evidence가 아닌 매핑된 것만 → 입력 토큰 80% 감소.

#### 28.2.2 used_evidence_ids 환각 안전망

LLM이 만든 used_evidence_ids 중 실제 존재하지 않는 ID 차단:

```python
# backend/services/llm_response_parser.py
class LLMHallucinatedEvidenceError(Exception): ...

def validate_used_evidence_ids(result, available_ids):
    invalid = set(result["used_evidence_ids"]) - set(available_ids)
    if invalid:
        raise LLMHallucinatedEvidenceError(f"환각 ID: {invalid}")
```

이미 적용. NOAPI-P2.

#### 28.2.3 표 항목 별도 처리 (LLM 우회)

`is_table_item=True` + `fill_mode='table_input'` 인 문항은 LLM 호출 X, frontend 직접 입력:

```jsx
// web-react/src/features/pages/draft-v2/Step3Draft.jsx
{question.is_table_item ? (
  <TableCellGrid
    headerCells={ts.header_cells}
    dataRows={ts.data_rows}
    onCellChange={...}
  />
) : (
  <DraftTextarea ... />
)}
```

**효과**: 표 8개 × 30초 = 4분 절약.

#### 28.2.4 profile_mapping 자동 (LLM 우회)

`fill_mode='profile_mapping'` 인 문항 (기업명/대표자/사업자번호 등)은 `company_schema_json.schema` 에서 자동 채움.

```js
const profileFields = question.profile_mapping?.fields  // ["name", "representative"]
const autoFilled = profileFields.reduce((acc, k) => ({ ...acc, [k]: companyData[k] }), {})
```

**효과**: 5~10개 문항 자동 채움 = 5분 절약.

#### 28.2.5 Streaming (SSE)

`draft_writer` 의 chunked 응답을 SSE로 frontend에 실시간 전달:

```python
@router.post("/write-draft-item-stream")
async def stream(req):
    async def event_gen():
        async for chunk in provider.draft_writer_stream(...):
            yield f"data: {json.dumps({'token': chunk})}\n\n"
    return EventSourceResponse(event_gen())
```

frontend EventSource:
```js
const es = new EventSource(`/api/analysis/write-draft-item-stream?...`)
es.onmessage = (e) => setDraft(prev => prev + JSON.parse(e.data).token)
```

**효과**: 사용자 체감 시간 60% 단축 (첫 토큰까지 1초).

#### 28.2.6 batch 모드 (여러 문항 1 호출)

작은 문항 5개를 1번 LLM 호출로 묶기:

```python
prompt = "다음 5개 항목의 초안을 JSON으로 작성하세요...\n\n{문항1}\n{문항2}\n..."
result = await provider.draft_writer_batch(prompt, max_tokens=5000)
# JSON parse → 5개 문항에 분배
```

**효과**: API 호출 overhead 80% 감소.

**리스크**: 한 문항 실패 시 5개 다 실패.

#### 28.2.7 cached draft (input_hash 일치 시)

`ai_call_logs.input_hash` 같으면 이전 결과 재사용. 사용자가 같은 문항 재작성 요청 안 했을 때.

**조건**:
- 동일 question_id
- 동일 mapping_result (evidence_ids 같음)
- 동일 company_schema_json

#### 28.2.8 모델 분기 (cost vs quality)

| 문항 유형 | 모델 |
|----------|------|
| 짧은 사실 (~30자) | gpt-4o-mini |
| 일반 서술 (200~400자) | gpt-4o |
| 핵심 서술 (사업화/기술성) | gpt-4o or Anthropic Sonnet |
| 최종 손질 (사용자 명시) | Anthropic Opus (premium_final_writer) |

`.env`의 `OPENAI_MODEL_DRAFT` + 추가 `OPENAI_MODEL_DRAFT_CRITICAL` 같은 분리.

### 28.3 write-all-drafts 최적화

#### 28.3.1 병렬 실행 (BackgroundTasks)

35개 문항을 순차 → 5개씩 병렬:

```python
async def write_all_drafts(session_id):
    questions = get_questions(session_id)
    semaphore = asyncio.Semaphore(5)  # TPM 한도 고려

    async def write_one(q):
        async with semaphore:
            return await write_draft_item(q)

    results = await asyncio.gather(*[write_one(q) for q in questions])
```

**효과**: 35분 → 7분.

#### 28.3.2 우선순위 큐

`evidence count` 많은 문항 먼저 (사용자가 빨리 봄). Evidence 부족한 문항은 사용자 보완 대기.

### 28.4 frontend 최적화

#### 28.4.1 좌 트리 lazy

`FormTreePanel.jsx` — 100+ 문항 트리 가상화 (react-window).

#### 28.4.2 inline 편집 debounce

textarea onChange → 500ms debounce → DB 저장 (overflow 방지).

#### 28.4.3 표 grid 가상화

큰 표 (50+ 행) 는 react-virtual로 가상화.

### 28.5 사용자 인터랙션 개선

#### 28.5.1 "이 부분 다시 써줘" 보완 대화

```js
chatApi.draftAssist({
  sessionId,
  questionId,
  currentDraft,
  userMessage: '구체적으로 다시 써줘'
})
```

backend `chat.py`. draft_rewriter LLM 호출.

#### 28.5.2 evidence 강조 표시

draft 안의 인용된 evidence를 hover하면 원본 evidence panel 표시 → 사용자 신뢰도 ↑.

#### 28.5.3 진행률 표시

35문항 중 N개 완료. 색상 분류:
- 회색: pending
- 노랑: draft (작성됨, 미확정)
- 초록: approved
- 빨강: needs_revision (Step4 평가 후)

### 28.6 Step3 측정 + 개선 우선순위

| 우선순위 | 항목 | 예상 효과 | 난이도 |
|---------|------|----------|--------|
| 1 | write-all-drafts 병렬 (semaphore=5) | 시간 80%↓ | 작음 |
| 2 | streaming (SSE) | UX 60%↑ | 중간 |
| 3 | profile_mapping 자동 fill | 5문항 자동 | 작음 |
| 4 | cached draft (input_hash) | 재작성 비용 0 | 중간 |
| 5 | batch 모드 (5문항 1호출) | API overhead 80%↓ | 큼 |
| 6 | 모델 분기 (mini/4o/opus) | 비용 50%↓ 품질 유지 | 중간 |

---

## 29. Step 4 평가 — 성능 고도화 가이드

### 29.1 현재 흐름

```
POST /api/analysis/evaluate-draft
  → provider.draft_evaluator(drafts, notice_schema, eval_criteria)
  → 평가 점수 + 카테고리별 + topIssues + improvementProgress 반환
```

응답 시간: 15~30초 (모든 draft를 한번에 분석).

### 29.2 evaluate-draft 최적화 5가지

#### 29.2.1 평가기준별 분리 호출

평가기준이 4개(기술성/사업성/기대효과/수행역량)면 4번 병렬 호출:

```python
results = await asyncio.gather(*[
    provider.draft_evaluator(drafts, criterion=c, ...)
    for c in criteria
])
final = _merge_evaluations(results)
```

**효과**: 30초 → 10초 (병렬). 카테고리별 정확도 ↑.

#### 29.2.2 평가 캐시

draft가 변경 안 됐으면 평가 재실행 X.

```python
draft_hash = sha256(json.dumps([d.content for d in drafts]))
if last_eval.input_hash == draft_hash:
    return last_eval.result
```

#### 29.2.3 평가기준 매핑 활용

`eval_criteria_mappings.mapped_questions` 가 이미 있으면 그 문항만 평가:

```python
for criterion in criteria:
    target_drafts = [d for d in drafts if d.question_id in criterion.mapped_questions]
    result = await provider.draft_evaluator(target_drafts, criterion)
```

**효과**: 입력 토큰 50%↓.

#### 29.2.4 점수 보정 (rubric 기반)

LLM 점수가 oscillate (같은 draft에 90점/70점). rubric 명시:

```
prompt: "다음 rubric에 따라 0~100점.
        90~100: 모든 요소 포함, 구체 수치
        70~89: 대부분 포함, 일부 추상
        50~69: 기본 요소만
        0~49: 누락 많음"
```

#### 29.2.5 보완안 자동 적용 (applyImprovement)

평가 결과 `topIssues[].improvedText` 가 있으면 1-click 적용:

```js
const applyImprovement = async ({ section, improvedText }) => {
  const updated = await analysisApi.applyImprovement({ sessionId, questionId, improvedText })
  setDraft(updated.content)
}
```

backend `chat.py` 의 draft_rewriter 호출.

### 29.3 평가기준 매핑 (v0.2.1 V3)

`PATCH /api/analysis/eval-criteria-mappings/{id}`

사용자 편집 시:
- `mapped_by="user"` 자동 설정
- `history` JSON 배열에 append (mapped_at / old / new / actor)

```sql
-- 예시
SELECT json_array_length(history) FROM eval_criteria_mappings WHERE id='crit_001';
-- 5  ← 5번 편집됨
```

frontend `web-react/src/lib/evalCriteriaMappingAdapter.js` 의 8개 export.

### 29.4 frontend 평가 UI

`Step4Evaluation.jsx`:
- 종합 점수 (currentScore) + expectedImprovement + passLine
- 카테고리 카드 4개 (기술성/사업성/...)
- topIssues 카드 — priority별
- improvementProgress — 적용/진행/대기 통계
- "보완안 적용" 버튼 → applyImprovement

### 29.5 Step4 측정 + 개선 우선순위

| 우선순위 | 항목 | 예상 효과 | 난이도 |
|---------|------|----------|--------|
| 1 | 평가기준별 병렬 호출 | 시간 70%↓ | 작음 |
| 2 | 평가 캐시 (draft_hash) | 재평가 비용 0 | 작음 |
| 3 | rubric 명시 | 점수 안정성 ↑ | 작음 |
| 4 | applyImprovement 1-click | UX ↑ | 중간 |
| 5 | mapped_questions 활용 | 토큰 50%↓ | 작음 |

---

## 30. 통합 측정 + 개선 우선순위 정리

### 30.1 전체 사용자 여정 시간 (현재)

| Step | 시간 | 사용자 액션 |
|------|------|------------|
| Step1 (자료 업로드) | 1~3분 | 4개 파일 선택 + 업로드 |
| Step2 (분석) | 1~2분 | 자동 분석 대기 |
| Step3 (초안) | 20~30분 | 35문항 작성 (직렬) |
| Step4 (평가) | 30초 | 평가 결과 검토 |
| Step5 (export) | 5초 | 다운로드 |
| **합계** | **22~35분** | |

### 30.2 개선 후 예상 시간

| Step | 시간 | 개선 적용 |
|------|------|----------|
| Step1 | 1~3분 | (변화 없음) |
| Step2 | 30초~1분 | hybrid + cache + pre-classification |
| Step3 | **5~10분** | 병렬 5 + streaming + profile auto |
| Step4 | 10초 | 병렬 + cache |
| Step5 | 5초 | (변화 없음) |
| **합계** | **7~14분** | **60% 단축** |

### 30.3 비용 영향

| 항목 | 현재 (35문항) | 개선 후 |
|------|--------------|--------|
| parse-form | ~$0.08 | ~$0.04 (cache hit) |
| parse-notice | ~$0.005 | ~$0.005 |
| draft × 35 | ~$1.05 | ~$0.50 (mini/4o 분기 + batch) |
| evaluate | ~$0.05 | ~$0.03 (cache + 병렬) |
| **합계** | **~$1.20** | **~$0.60 (50% 절감)** |

### 30.4 우선순위 통합 로드맵

#### Phase 5 H1 (다음 작업, 2주)
1. Step3 write-all-drafts 병렬 (semaphore=5) ← **가장 큰 효과**
2. parse-form Hybrid chunk rate limiter
3. profile_mapping 자동 fill
4. Step4 평가기준별 병렬

#### Phase 5 H2 (3주)
5. Streaming (SSE) — Step3 write-draft-item
6. parse-form input caching (ai_call_logs.input_hash)
7. Step4 평가 캐시
8. mapping_pipeline progress SSE

#### Phase 5 H3 (4주)
9. write-all-drafts batch (5문항 1호출)
10. Model 분기 (mini/4o/opus per question)
11. Layout pre-classification
12. cached draft per question

#### Phase 5 H4 / v0.3 (1~2개월)
13. Postgres + JSONB 마이그레이션
14. pgvector 통합 (ChromaDB 대체)
15. WebSocket progress
16. multi-user 인증

### 30.5 성능 모니터링 대시보드 (제안)

`/api/analysis/dashboard/performance` (미구현):

```json
{
  "avg_step2_time_ms": 75000,
  "avg_step3_time_per_question_ms": 45000,
  "tpm_429_rate_24h": 0.05,
  "cache_hit_rate": 0.0,
  "total_cost_krw_today": 12500,
  "total_cost_krw_month": 285000
}
```

`ai_call_logs` 집계로 산출. Grafana / Streamlit 가능.

### 30.6 측정 지표 (KPI)

| 지표 | 측정 | 목표 |
|------|------|------|
| Time-to-first-draft (TTFD) | Step1 시작 ~ Step3 첫 문항 작성 완료 | < 5분 |
| Total session time | Step1 ~ Step5 export | < 15분 |
| LLM 평균 cost/session | ai_call_logs.cost_estimate_krw SUM | < ₩1500 |
| 429 rate | (failed_429 / total_calls) | < 1% |
| parse_error rate | parse_error / total_calls | < 0.5% |
| 사용자 inline 편집률 | edited_chars / generated_chars | (참고 지표) |

### 30.7 회귀 방지 — 안전망 (현재)

| 안전망 | 갯수 | 비고 |
|--------|------|------|
| grep CI (B3) | 5 rules | V2 정책 회귀 자동 감지 |
| pytest backend smoke | 14 tests | session/parse/mapping/draft 흐름 |
| pytest NOAPI parser | 26 tests | JSON 펜스/trailing/환각 안전망 |
| pytest NOAPI readiness | 26 tests | token budget + fixture schema |
| vitest frontend | 116 tests | adapter/diagnostic |
| dependency-free smoke | 84 tests | 외부 framework 없음 |
| Playwright e2e | 3 시나리오 | happy-path + eval-criteria + diagnostic |
| **합계** | **274** | |

### 30.8 새 최적화 작업 가이드

1. **측정 먼저** — 최적화 전 ai_call_logs로 현재 시간/비용 측정
2. **단위 테스트** — 변경 전 pytest 통과 확인
3. **A/B 비교** — old vs new 시간/비용/정확도 표 작성
4. **점진 적용** — env flag로 분기 (`USE_PARALLEL_DRAFTS=true`)
5. **회귀 추적** — ai_call_logs.status 비율 모니터링 (1주)
6. **STATUS / TODO 갱신** — `local/2_work/`에 변경 기록

---

## 31. 마무리

이 README는 **2000+ 줄의 매뉴얼**입니다. 한 번에 다 읽지 마시고, 다음 가이드를 따라 필요한 섹션만 보세요:

### 🎯 역할별 최소 읽기

| 역할 | 필독 섹션 |
|------|----------|
| **새 팀원 (전체)** | §1, §2, §4, §15 |
| **백엔드 개발자** | §5, §9, §10, §26, §27, §28, §29 |
| **프론트엔드 개발자** | §6, §7, §9, §27, §28 |
| **DB / 데이터** | §10, §26, §30 |
| **DevOps / 인프라** | §9, §11, §13, §14 |
| **PM / 기획** | §1, §3, §7, §8, §30 |
| **성능 최적화 담당** | §27, §28, §29, §30 |

### 📚 추가 학습 자료

- [§16.2 외부 링크](#162-외부-링크) — Drive / Notion
- [§16.3 API 문서](#163-api-문서) — OpenAI / Anthropic / 공공데이터
- [§16.4 기술 문서](#164-기술-문서) — FastAPI / React / Vite / shadcn

### 💬 문의

- **GitHub Issues**: 버그/기능 요청
- **GitHub Discussions**: 일반 질문
- **Notion**: 기획/회의록

문서 개선 제안은 PR 환영합니다!

**Happy coding! 🚀**
