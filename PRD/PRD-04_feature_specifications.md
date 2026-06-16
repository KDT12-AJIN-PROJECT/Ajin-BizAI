# PRD-04: 기능 명세 (Feature Specifications)

> **문서 버전** 1.0 | **선행 문서** PRD-03 | **후행 문서** PRD-05  
> **목적** F-01~F-10 모든 기능의 코드 수준 완전 명세  
> **규칙** 이 문서의 모든 함수명·파일명·변수명은 고정이다. 변경하지 말 것.

---

## F-01: 공고 수집 엔진 (Notice Collection Engine)

### 사용자 스토리
> AS 기획팀 담당자, I WANT 여러 정부 사이트의 공고를 한 곳에서 보고 싶다,  
> SO THAT 공고를 놓치지 않고 빠르게 파악할 수 있다.

### 수용 기준 (Acceptance Criteria)
- [ ] 4개 공공 API에서 공고를 병렬로 수집한다
- [ ] 하나의 API가 실패해도 나머지 결과는 정상 표시된다
- [ ] 중복 공고(같은 제목+날짜)는 1건만 표시된다
- [ ] 모든 API 실패 시 Mock 데이터 3건을 표시하고 경고 배너를 띄운다
- [ ] 수집 결과는 sessionStorage에 1시간 캐시한다

### 4.1.1 데이터 소스

| 소스 | 환경변수 | 기본 엔드포인트 | 응답 배열 키 |
|------|---------|--------------|------------|
| 기업마당 | `VITE_BIZINFO_API_URL` | `https://www.bizinfo.go.kr/cm/search/searchList.do` | `jsonArray` |
| 과기부 | `VITE_MSIT_API_URL` | `https://www.msit.go.kr/...` | `response.body.items` |
| 중기부 | `VITE_MSS_API_URL` | `https://www.mss.go.kr/...` | `pblancList` |
| 창진원 | `VITE_KSTARTUP_API_URL` | `https://www.k-startup.go.kr/...` | `items` |

### 4.1.2 fetchAllNotices() — 완전한 구현 코드

```javascript
// src/api/noticesApi.js

import { env } from '../config/env'
import { normalizeNotice, dedupeNotices } from '../features/notices/utils/normalize'
import { STORAGE_KEYS, STORAGE_TTL } from '../constants/storageKeys'

// ─── Mock 데이터 (API 전체 실패 시 폴백) ───────────────────────────────
const MOCK_NOTICES_RAW = [
  {
    pblancNm: '2026년 스마트공장 고도화 지원사업',
    reqstBeginEndDe: '2026-04-01 ~ 2026-05-10',
    trgetNm: '중소/중견 제조기업 (스마트공장 구축·고도화 희망 기업)',
    bsnsSumryCn: '자동차 부품 생산 라인 자동화 및 품질고도화 지원',
    suptCn: '장비도입 및 컨설팅 비용 지원 (최대 2억원, 정부 50%)',
    areaNm: '전국',
    pblancUrl: 'https://www.bizinfo.go.kr/',
  },
  {
    pblancNm: '제조DX 전환 바우처 2026',
    reqstBeginEndDe: '2026-04-15 ~ 2026-06-01',
    trgetNm: '디지털 전환이 필요한 중소제조기업',
    bsnsSumryCn: '데이터 기반 공정개선 및 에너지 절감 솔루션 도입',
    suptCn: '바우처 및 실증 비용 지원 (최대 5,000만원)',
    areaNm: '전국',
    pblancUrl: 'https://www.bizinfo.go.kr/',
  },
  {
    pblancNm: '중소기업 R&D 역량강화 지원사업',
    reqstBeginEndDe: '2026-05-01 ~ 2026-05-31',
    trgetNm: '업력 3년 이상 중소기업',
    bsnsSumryCn: 'AI·자동화 기술 개발 R&D 과제 지원',
    suptCn: '과제당 최대 1억원 (정부 75%)',
    areaNm: '전국',
    pblancUrl: 'https://www.bizinfo.go.kr/',
  },
]

// ─── URL 빌더 ──────────────────────────────────────────────────────────
function buildUrl(baseUrl, params) {
  const usp = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).length > 0) {
      usp.set(key, String(value))
    }
  })
  return `${baseUrl}?${usp.toString()}`
}

// ─── JSON/XML 안전 파싱 ────────────────────────────────────────────────
async function safeFetchJson(url) {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 10000) // 10초 타임아웃
  try {
    const res = await fetch(url, { signal: controller.signal })
    if (!res.ok) throw new Error(`HTTP_${res.status}`)
    const text = await res.text()
    try {
      return JSON.parse(text)
    } catch {
      // XML 응답 처리
      const parser = new DOMParser()
      const xml = parser.parseFromString(text, 'application/xml')
      const items = [...xml.querySelectorAll('item')]
      return {
        items: items.map((item) =>
          [...item.children].reduce((acc, node) => {
            acc[node.tagName] = node.textContent
            return acc
          }, {})
        ),
      }
    }
  } finally {
    clearTimeout(timeoutId)
  }
}

// ─── 배열 추출 (소스별 경로 상이) ─────────────────────────────────────
function parseItems(agency, data) {
  if (agency === '기업마당') return data?.jsonArray ?? data?.items ?? []
  if (agency === '과기부')   return data?.response?.body?.items ?? []
  if (agency === '중기부')   return data?.pblancList ?? data?.items ?? []
  if (agency === '창진원')   return data?.items ?? data?.data ?? []
  return []
}

// ─── 캐시 관리 ────────────────────────────────────────────────────────
function getCachedNotices() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEYS.NOTICES_CACHE)
    if (!raw) return null
    const { data, timestamp } = JSON.parse(raw)
    if (Date.now() - timestamp > STORAGE_TTL.NOTICES_CACHE) return null
    return data
  } catch { return null }
}

function setCachedNotices(notices) {
  try {
    sessionStorage.setItem(STORAGE_KEYS.NOTICES_CACHE, JSON.stringify({
      data: notices,
      timestamp: Date.now(),
    }))
  } catch { /* 저장 실패 무시 */ }
}

// ─── 메인 수집 함수 ────────────────────────────────────────────────────
export async function fetchAllNotices() {
  // 1. 캐시 확인
  const cached = getCachedNotices()
  if (cached) return { notices: cached, errors: [] }

  const today = new Date()
  const ago90 = new Date(); ago90.setDate(today.getDate() - 90)
  const fmt = (d) => d.toISOString().slice(0, 10)

  const configs = [
    {
      agency: '기업마당',
      url: buildUrl(env.bizInfoUrl, {
        dataType: 'json',
        searchNm: env.noticeSearchNm || '자동차 부품',
        sortId: 'L',
      }),
    },
    {
      agency: '과기부',
      url: buildUrl(env.msitUrl, {
        pageNo: 1, numOfRows: 50, returnType: 'json',
      }),
    },
    {
      agency: '중기부',
      url: buildUrl(env.mssUrl, {
        pageNo: 1, numOfRows: 50,
        startDate: fmt(ago90), endDate: fmt(today),
      }),
    },
    {
      agency: '창진원',
      url: buildUrl(env.kstartupUrl, {
        page: 1, perPage: 50, returnType: 'json',
      }),
    },
  ]

  const settled = await Promise.allSettled(
    configs.map(async (cfg) => {
      const data = await safeFetchJson(cfg.url)
      const items = parseItems(cfg.agency, data)
      return items.map((item) => normalizeNotice(item, cfg.agency))
    })
  )

  const notices = []
  const errors = []
  settled.forEach((result, idx) => {
    if (result.status === 'fulfilled') {
      notices.push(...result.value)
    } else {
      errors.push(`${configs[idx].agency}: ${result.reason?.message ?? '요청 실패'}`)
    }
  })

  // 2. 전체 실패 시 Mock 폴백
  if (notices.length === 0 && env.useMockWhenFailed) {
    const mockNotices = MOCK_NOTICES_RAW.map((item) => normalizeNotice(item, '샘플데이터'))
    errors.push('외부 API 호출 실패로 샘플 데이터를 표시합니다. API 키 설정을 확인하세요.')
    return { notices: dedupeNotices(mockNotices), errors }
  }

  const deduped = dedupeNotices(notices)
  setCachedNotices(deduped)
  return { notices: deduped, errors }
}
```

### 4.1.3 normalizeNotice() — 완전한 구현 코드

```javascript
// src/features/notices/utils/normalize.js

// ─── 날짜 파싱 ─────────────────────────────────────────────────────────
function parseEndDate(str) {
  if (!str) return null
  // 형식 1: "2026-01-01 ~ 2026-03-31" → 마감일 추출
  const m1 = str.match(/(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})/)
  if (m1) return new Date(m1[2])
  // 형식 2: "20260331" → YYYYMMDD
  const m2 = str.match(/^(\d{4})(\d{2})(\d{2})$/)
  if (m2) return new Date(`${m2[1]}-${m2[2]}-${m2[3]}`)
  // 형식 3: "2026.03.31"
  const m3 = str.match(/(\d{4})\.(\d{2})\.(\d{2})/)
  if (m3) return new Date(`${m3[1]}-${m3[2]}-${m3[3]}`)
  return null
}

// ─── ID 생성 (title + date 해시) ──────────────────────────────────────
function makeId(title, date) {
  const str = `${title || ''}${date ? date.toISOString().slice(0, 10) : ''}`
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash).toString(36)
}

// ─── 소스별 필드 매핑 ──────────────────────────────────────────────────
const FIELD_MAP = {
  '기업마당': {
    title: ['pblancNm'],
    content: ['bsnsSumryCn', 'bizCn'],
    target: ['trgetNm', 'aplyQlfcCn'],
    benefit: ['suptCn', 'suptDtlCn'],
    documents: ['sbmsDocCn'],
    limit: ['lmtCn', 'rstrCn'],
    region: ['areaNm'],
    category: ['bsnsCl', 'bsnsKndNm'],
    period: ['reqstBeginEndDe'],
    url: ['pblancUrl'],
    attachmentUrl: ['atchFileUrl', 'atchFileNm'],
    jrsdInsttNm: ['jrsdInsttNm'],
    excInsttNm: ['excInsttNm'],
    reqstMthPapersCn: ['reqstMthPapersCn'],
    refrncNm: ['refrncNm'],
  },
  '과기부': {
    title: ['pblancNm', 'noticNm'],
    content: ['bsnsSumryCn'],
    target: ['trgetNm'],
    benefit: ['suptCn'],
    region: ['areaNm'],
    period: ['reqstBeginEndDe'],
    url: ['pblancUrl'],
  },
  '중기부': {
    title: ['pblancNm'],
    content: ['bsnsSumryCn'],
    target: ['trgetNm'],
    benefit: ['suptCn'],
    region: ['areaNm'],
    period: ['reqstBeginEndDe'],
    url: ['pblancUrl'],
  },
  '창진원': {
    title: ['pblancNm', 'biz_nm'],
    content: ['bsnsSumryCn', 'biz_cn'],
    target: ['trgetNm'],
    benefit: ['suptCn'],
    region: ['areaNm'],
    period: ['reqstBeginEndDe'],
    url: ['pblancUrl', 'url'],
  },
}

function extractField(raw, fieldKeys) {
  if (!Array.isArray(fieldKeys)) return ''
  for (const key of fieldKeys) {
    if (raw[key]) return String(raw[key]).trim()
  }
  return ''
}

export function normalizeNotice(raw, agency) {
  const map = FIELD_MAP[agency] ?? FIELD_MAP['기업마당']
  const get = (field) => extractField(raw, map[field] ?? [])

  const period = get('period')
  const date = parseEndDate(period)

  const notice = {
    id: '',
    origin: agency,
    title: get('title') || '제목 없음',
    content: get('content'),
    target: get('target'),
    benefit: get('benefit'),
    documents: get('documents'),
    limit: get('limit'),
    region: get('region') || '전국',
    category: get('category'),
    hashTags: '',
    period,
    date,
    url: get('url'),
    attachmentUrl: get('attachmentUrl'),
    rceptEngnHmpgUrl: raw.rceptEngnHmpgUrl || '',
    jrsdInsttNm: get('jrsdInsttNm'),
    excInsttNm: get('excInsttNm'),
    reqstMthPapersCn: get('reqstMthPapersCn'),
    refrncNm: get('refrncNm'),
    ajin_similarity: 0,
    evaluationCriteria: null,
    requiredDocChecklist: null,
    supportAmountDetail: null,
  }

  notice.id = makeId(notice.title, notice.date)
  return notice
}

// ─── 중복 제거 ─────────────────────────────────────────────────────────
export function dedupeNotices(notices) {
  const seen = new Set()
  return notices.filter((n) => {
    if (seen.has(n.id)) return false
    seen.add(n.id)
    return true
  })
}

// ─── 첨부파일 파싱 ────────────────────────────────────────────────────
export function parseAttachmentList(notice) {
  const attachments = []
  if (notice.attachmentUrl) {
    // "파일명|URL|파일명2|URL2" 또는 단순 URL
    const parts = notice.attachmentUrl.split('|')
    if (parts.length >= 2) {
      for (let i = 0; i < parts.length - 1; i += 2) {
        const name = parts[i]?.trim()
        const url = parts[i + 1]?.trim()
        if (name && url) {
          const ext = name.split('.').pop()?.toUpperCase() ?? 'FILE'
          attachments.push({ name, url, type: ext })
        }
      }
    } else if (parts[0]?.startsWith('http')) {
      attachments.push({
        name: '공고문',
        url: parts[0],
        type: 'PDF',
      })
    }
  }
  return attachments
}
```

---

## F-02: AI 적합도 매칭 (AI Matching Score)

### 사용자 스토리
> AS 기획팀 담당자, I WANT 공고가 우리 회사에 얼마나 맞는지 수치로 보고 싶다,  
> SO THAT 1,000건 중 실제로 검토할 10~20건만 골라낼 수 있다.

### 수용 기준
- [ ] 기업 프로필 텍스트와 공고 텍스트의 유사도를 0~1 사이 숫자로 반환한다
- [ ] 임계값(기본 0.02) 미만 공고는 필터링된다
- [ ] 적합도 색상: >0.05 녹색, 0.02~0.05 주황, <0.02 회색
- [ ] 빈 프로필이면 0을 반환한다 (에러 없음)

### 4.2.1 완전한 구현 코드

```javascript
// src/features/notices/utils/match.js

// ─── 한국어+영문 토크나이저 ────────────────────────────────────────────
export function tokenize(text) {
  return String(text ?? '')
    .toLowerCase()
    .replace(/[^0-9a-zA-Z가-힣\s]/g, ' ')
    .split(/\s+/)
    .filter((t) => t.length > 1)
}

// ─── Jaccard 유사도 (MVP v1.0) ────────────────────────────────────────
export function similarityScore(profileText, noticeCorpus) {
  const p = new Set(tokenize(profileText))
  const n = new Set(tokenize(noticeCorpus))
  if (p.size === 0 || n.size === 0) return 0
  let intersection = 0
  p.forEach((t) => { if (n.has(t)) intersection++ })
  const union = p.size + n.size - intersection
  return union > 0 ? intersection / union : 0
}

// ─── 공고 코퍼스 생성 ──────────────────────────────────────────────────
export function buildNoticeCorpus(notice) {
  return [
    notice.title,
    notice.content,
    notice.target,
    notice.benefit,
    notice.category,
    notice.hashTags,
    notice.region,
  ].filter(Boolean).join(' ')
}

// ─── 기업 프로필 코퍼스 생성 ───────────────────────────────────────────
export function buildProfileCorpus(profile, notiKeywords = '') {
  return [
    profile.field,
    profile.summary,
    profile.strategy,
    profile.industry,
    profile.keywords?.join(' '),
    notiKeywords,
  ].filter(Boolean).join(' ')
}

// ─── 전체 공고 적합도 일괄 계산 ────────────────────────────────────────
export function computeAllSimilarities(notices, profile, notiKeywords) {
  const profileCorpus = buildProfileCorpus(profile, notiKeywords)
  return notices.map((notice) => ({
    ...notice,
    ajin_similarity: similarityScore(profileCorpus, buildNoticeCorpus(notice)),
  }))
}

// ─── 적합도 뱃지 스타일 ────────────────────────────────────────────────
export function getMatchScoreBadgeVariant(score) {
  if (score >= 0.05) return 'success'   // 녹색 — 높은 적합도
  if (score >= 0.02) return 'warning'   // 주황 — 보통 적합도
  return 'secondary'                    // 회색 — 낮은 적합도
}

export function formatMatchScore(score) {
  return `${(score * 100).toFixed(1)}%`
}
```

---

## F-03: 공고 검색 & 필터링

### 4.3.1 완전한 필터링 코드

```javascript
// src/features/notices/utils/filtering.js

export function filterNotices(notices, filters) {
  const {
    matchMode,       // 'AI적합도' | '키워드'
    threshold,       // number (0.01~0.1)
    searchTitle,     // string
    selectedKeywords,// string[]
    selectedRegions, // string[]
    selectedSizes,   // string[]
  } = filters

  return notices.filter((notice) => {
    // 1. 적합도 임계값 필터 (matchMode가 '적합도'일 때만)
    if (matchMode === 'AI적합도' && notice.ajin_similarity < threshold) return false

    // 2. 제목 검색 (대소문자 무시)
    if (searchTitle && !notice.title.toLowerCase().includes(searchTitle.toLowerCase())) return false

    // 3. 키워드 필터 (선택한 키워드 중 하나라도 공고에 포함되면 통과)
    if (selectedKeywords.length > 0) {
      const corpus = buildNoticeCorpus(notice).toLowerCase()
      const hasKeyword = selectedKeywords.some((kw) => corpus.includes(kw.toLowerCase()))
      if (!hasKeyword) return false
    }

    // 4. 지역 필터 (전국은 모든 지역 공고에 매칭)
    if (selectedRegions.length > 0) {
      const region = notice.region || ''
      const hasRegion = region.includes('전국') ||
        selectedRegions.some((r) => region.includes(r))
      if (!hasRegion) return false
    }

    // 5. 기업 규모 필터
    if (selectedSizes.length > 0) {
      const target = (notice.target || '').toLowerCase()
      const hasSize = selectedSizes.some((sz) => {
        if (sz === '중소') return target.includes('중소')
        if (sz === '중견') return target.includes('중견')
        if (sz === '대기업') return target.includes('대기업')
        if (sz === '창업') return target.includes('창업') || target.includes('스타트업')
        return false
      })
      if (!hasSize) return false
    }

    return true
  })
}

export function sortNotices(notices, sortBy) {
  const sorted = [...notices]
  switch (sortBy) {
    case '적합도순':
      return sorted.sort((a, b) => b.ajin_similarity - a.ajin_similarity)
    case '최신순':
      return sorted.sort((a, b) => {
        if (!a.date && !b.date) return 0
        if (!a.date) return 1
        if (!b.date) return -1
        return b.date - a.date
      })
    case '마감일 가까운 순':
      return sorted.sort((a, b) => {
        const now = Date.now()
        const dA = a.date ? a.date - now : Infinity
        const dB = b.date ? b.date - now : Infinity
        return dA - dB
      })
    case '마감일 늦은 순':
      return sorted.sort((a, b) => {
        const now = Date.now()
        const dA = a.date ? a.date - now : -Infinity
        const dB = b.date ? b.date - now : -Infinity
        return dB - dA
      })
    default:
      return sorted
  }
}

export function paginateNotices(notices, page, pageSize) {
  const totalPages = Math.max(1, Math.ceil(notices.length / pageSize))
  const safePage = Math.min(Math.max(1, page), totalPages)
  const start = (safePage - 1) * pageSize
  return {
    items: notices.slice(start, start + pageSize),
    page: safePage,
    totalPages,
    totalCount: notices.length,
  }
}

// 필터 옵션 자동 추출 (공고 목록에서 동적 생성)
export function extractFilterOptions(notices) {
  const keywordSet = new Set()
  const regionSet = new Set()

  notices.forEach((n) => {
    // 카테고리·해시태그에서 키워드 추출
    const tokens = tokenize(`${n.category} ${n.hashTags}`)
    tokens.forEach((t) => { if (t.length > 1) keywordSet.add(t) })
    // 지역
    if (n.region && !n.region.includes('전국')) regionSet.add(n.region)
  })

  return {
    keywordOptions: [...keywordSet].slice(0, 30), // 최대 30개
    regions: ['전국', ...regionSet].sort(),
    sizes: ['중소', '중견', '대기업', '창업'],
  }
}
```

---

## F-04: 공고 상세 — 평가기준 AI 파싱

### 4.4.0 상단 버튼 바 명세 (순서·텍스트 고정)

> **중요**: 버튼 텍스트 "빠른 조언" 은 절대 "빠른 초안"으로 쓰지 않는다.

```jsx
// DetailPage 상단 버튼 바 — 순서 및 레이블 고정
// import { Phone, ExternalLink, FileText, Sparkles, Clock } from 'lucide-react'

<div className="flex items-center justify-between">
  <Button variant="ghost" size="sm" onClick={onBack}>
    <ArrowLeft className="w-4 h-4" aria-hidden="true" /> 목록으로
  </Button>

  <div className="flex items-center gap-2 flex-wrap">
    {notice.url && (
      <Button variant="outline" size="sm" asChild>
        <a href={notice.url} target="_blank" rel="noreferrer">
          <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" /> 공고원문 보러가기
        </a>
      </Button>
    )}
    <Button variant="outline" size="sm" onClick={() => setShowContactModal(true)}>
      <Phone className="w-3.5 h-3.5" aria-hidden="true" /> 문의 및 신청방법
    </Button>
    <Button size="sm" variant="outline" onClick={() => navigate(PAGE.QUICK_DRAFT, { notice })}>
      <FileText className="w-3.5 h-3.5" aria-hidden="true" /> 빠른 조언
    </Button>
    <Button size="sm" onClick={() => navigate(PAGE.CHAT_DRAFT, { notice })}>
      <Sparkles className="w-3.5 h-3.5" aria-hidden="true" /> AI 대화형 작성
    </Button>
  </div>
</div>

{/* D-Day 마감 경고 — 마감 7일 이내만 표시 */}
{daysLeft !== null && daysLeft >= 0 && daysLeft <= 7 && (
  <div className="flex justify-end">
    <div className="flex items-center gap-1 text-xs text-amber-600 font-medium bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
      <Clock className="w-3 h-3" aria-hidden="true" />
      D-{daysLeft} 마감
    </div>
  </div>
)}
```

### 4.4.1 공고 상세 전체 레이아웃 (화면 구성 고정)

```
[상단 버튼 바]
  ← 목록으로 | 공고원문 보러가기 | 문의 및 신청방법 | 빠른 조언 | AI 대화형 작성
  (D-N 마감 라벨: 마감 7일 이내만 표시, 우측 정렬)

[타이틀 카드] (border-l-4 border-l-primary)
  공고명 (text-lg font-bold) ─────────────────── [D-N 뱃지: 빨간색 우상단]
  소관기관 | 수행기관 | 지역 | 신청기간 | 적합도 N.N%

──────────────── 2열 그리드 (grid-cols-2 gap-3) ────────────────

좌열                                우열
─────────────────────               ──────────────────────────────
지원 대상 카드                        필수 비용 편성 안내 카드
  지원대상 (텍스트)                     ┌─ [AI 요약] 버튼 (우상단) ─┐
  신청자격 (텍스트)                     • 회계정산 수수료 (총사업비 규모별)
                                        • 교육비 100만원 필수 편성
지원내용 카드 (체크마크 항목)           • 기술임치비 45만원 필수 편성
  ✅ 솔루션 구축/컨설팅/기획지원         • 현물 편성 가능 범위
  ✅ 구축 목표 수준                     └───────────────────────────┘
  ✅ 필수 기술 요건
  ✅ 컨소시엄 구성 여부                평가 기준 요약 카드
                                        우상단 뱃지: "선정 가능성 판단" (green)
지원혜택 카드 (2×N 그리드)             서면평가 항목·배점 태그
  [지원규모] 국비 최대 N%               가점 항목 태그 (green variant)
  [지원조건] 정부지원금 + 기업부담       정량 평가 기준 태그 (outline variant)
  [지원한도] N억원 ~ N억원              동점 처리 기준 (텍스트)
  [비용] 기업부담금 N% 이상
  [기간] 최대 N개월                   유의사항 카드
                                        🔴 신청 제외 대상 경고 (bg-red-50)
지원유의사항 카드                        원문 공고 확인 안내 텍스트
  ⚠️ 동시 수행 제한  (bg-amber-50)
  ⚠️ 참여제한 제재   (bg-amber-50)
  ⚠️ 중복 지원 금지  (bg-amber-50)

──────────────── 전체 너비 섹션 ────────────────

[제출 서류 체크리스트]
[공고문/첨부파일 다운로드]
[공고문 미리보기]  ← 연동 시 표시, 미연동 시 빈 상태 UI
```

### 4.4.2 신규 파싱 함수: parseSupportAmount(), parseCostBudget(), parseSupportContent()

```javascript
// src/features/notices/utils/evaluationParser.js 에 추가

/**
 * 지원혜택 텍스트에서 지원규모/조건/한도/비용/기간 파싱
 * @returns {{ maxRatio, condition, maxAmount, selfRatio, period } | null}
 */
export function parseSupportAmount(benefitText) {
  if (!benefitText) return null
  const result = {
    maxRatio: '',    // "국비 최대 50%"
    condition: '',   // "정부지원금 + 기업부담"
    maxAmount: '',   // "1억원 ~ 10억원"
    selfRatio: '',   // "기업부담금 30% 이상"
    period: '',      // "최대 12개월"
  }
  // 지원 비율: "N%" 패턴
  const ratioM = benefitText.match(/국비\s*최대\s*(\d+)%|정부\s*(\d+)%/)
  if (ratioM) result.maxRatio = `국비 최대 ${ratioM[1] || ratioM[2]}%`

  // 지원 한도: "N억원" 또는 "N억~M억" 패턴
  const amtM = benefitText.match(/(\d+억원?\s*~\s*\d+억원?|\d+억원?|\d{3,}만원)/)
  if (amtM) result.maxAmount = amtM[1]

  // 기업 부담금: "기업부담금 N% 이상"
  const selfM = benefitText.match(/기업부담금\s*(\d+)%|자부담\s*(\d+)%/)
  if (selfM) result.selfRatio = `기업부담금 ${selfM[1] || selfM[2]}% 이상`

  // 기간: "최대 N개월" 또는 "N년"
  const periodM = benefitText.match(/최대\s*(\d+)개월|최대\s*(\d+)년/)
  if (periodM) result.period = periodM[0]

  // 지원 조건
  if (benefitText.includes('정부지원금')) result.condition = '정부지원금 + 기업부담'

  return result
}

/**
 * 공고 텍스트에서 필수 비용 편성 안내 파싱
 * 예: "교육비 100만원 필수 편성", "기술임치비 45만원 필수"
 * @returns {string[]} 항목별 문자열 배열
 */
export function parseCostBudget(noticeText) {
  if (!noticeText) return []
  const items = []
  const patterns = [
    /교육비\s*[\d,]+만원[^.。\n]*/g,
    /기술임치비\s*[\d,]+만원[^.。\n]*/g,
    /회계정산\s*수수료[^.。\n]*/g,
    /현물\s*편성[^.。\n]*/g,
  ]
  patterns.forEach((re) => {
    const matches = noticeText.match(re)
    if (matches) items.push(...matches.map((m) => m.trim()))
  })
  return items.slice(0, 6) // 최대 6항목
}

/**
 * 지원내용 텍스트에서 체크마크 항목 파싱
 * 불릿(·, ○, □, -) 또는 번호 뒤에 오는 항목 추출
 * @returns {Array<{label: string, detail: string}>}
 */
export function parseSupportContentItems(benefitText) {
  if (!benefitText) return []
  const lines = benefitText
    .split(/\n|·|○|□|⊙/)
    .map((l) => l.replace(/^\s*[\d\-\.]+\s*/, '').trim())
    .filter((l) => l.length > 3 && l.length < 80)
  // 제목행과 상세행 분리 (짧은 줄이 제목, 긴 줄이 상세)
  const items = []
  for (let i = 0; i < lines.length && items.length < 6; i++) {
    const line = lines[i]
    const detail = lines[i + 1]?.length > lines[i].length ? lines[i + 1] : ''
    if (detail) i++
    items.push({ label: line, detail })
  }
  return items
}

/**
 * 지원제한사항 텍스트에서 경고 항목 파싱
 * @returns {Array<{title: string, desc: string}>}
 */
export function parseLimitItems(limitText) {
  if (!limitText) return []
  const KNOWN_LIMITS = [
    { keyword: '동시 수행',    title: '동시 수행 제한',  desc: '사업 수행 중 여부 확인 필요' },
    { keyword: '참여제한',     title: '참여제한 제재',   desc: '참여제한 제재 여부 확인' },
    { keyword: '중복 지원',    title: '중복 지원 금지',  desc: '동일·유사 사업계획서 중복 지원 여부' },
    { keyword: '사업자등록',   title: '사업자 등록 요건', desc: '유효한 사업자등록증 보유' },
  ]
  return KNOWN_LIMITS.filter((l) => limitText.includes(l.keyword))
}
```

### 4.4.3 규칙 기반 파싱 (LLM 없이도 동작)

```javascript
// src/features/notices/utils/evaluationParser.js

/**
 * 공고 텍스트에서 평가기준을 추출한다.
 * LLM 없이 규칙 기반으로 먼저 시도하고, 실패 시 LLM 폴백을 사용한다.
 */
export function parseEvaluationCriteria(text) {
  if (!text) return null

  const result = {
    faceItems: [],
    bonusItems: [],
    quantitativeItems: [],
    tiebreakerRule: '',
    totalScore: 0,
  }

  // 규칙 1: "서면평가" 표 파싱 — "항목명 N점" 패턴
  const facePattern = /([가-힣\w\s]{2,20})\s+(\d{1,3})\s*점/g
  let m
  while ((m = facePattern.exec(text)) !== null) {
    const name = m[1].trim()
    const score = parseInt(m[2], 10)
    if (score > 0 && score <= 100 && name.length >= 2) {
      result.faceItems.push({ name, score })
      result.totalScore += score
    }
  }

  // 규칙 2: 가점 항목 — "가점" 이후 불릿/번호 목록
  const bonusSection = text.match(/가점[^.]*?:(.*?)(?=\n\n|\z)/s)
  if (bonusSection) {
    const items = bonusSection[1].split(/\n|·|○|□/).map((s) => s.trim()).filter(Boolean)
    result.bonusItems = items.slice(0, 10)
  }

  // 규칙 3: 정량 평가 — 재무 지표 키워드
  const quantKeywords = ['매출액 증가율', '영업이익률', '부채비율', '수출실적', '고용 증가율']
  quantKeywords.forEach((kw) => {
    if (text.includes(kw)) result.quantitativeItems.push(kw)
  })

  // 규칙 4: 동점 처리
  const tieMatch = text.match(/동점[^.]*?(기업 규모|[가-힣\s]{5,30})[^.]*\./g)
  if (tieMatch) result.tiebreakerRule = tieMatch[0]

  // 규칙 기반 파싱 실패 시 null 반환 (LLM 폴백 신호)
  if (result.faceItems.length === 0) return null

  return result
}

// 공통 제출 서류 목록 (모든 공고에 기본 포함)
export const DEFAULT_DOCUMENT_CHECKLIST = [
  { name: '사업계획서 (신청서)', required: true, validityPeriod: null },
  { name: '사업자등록증명원', required: true, validityPeriod: '3개월 이내 발급' },
  { name: '중소기업 확인서 또는 중견기업 확인서', required: true, validityPeriod: '유효기간 내' },
  { name: '국세 완납증명서', required: true, validityPeriod: '3개월 이내 발급' },
  { name: '지방세 완납증명서', required: true, validityPeriod: '3개월 이내 발급' },
  { name: '법인인감증명서 또는 사용인감계', required: true, validityPeriod: '3개월 이내 발급' },
  { name: '최근 3개년 재무제표', required: true, validityPeriod: null },
  { name: '4대 사회보험 가입자 명부', required: false, validityPeriod: '1개월 이내 발급' },
  { name: '수출실적 확인서', required: false, validityPeriod: '해당 기업만' },
]
```

### 4.4.2 LLM 폴백 프롬프트 (word-for-word 고정)

```javascript
// src/api/lmStudioApi.js 내 평가기준 파싱 함수

export async function parseEvaluationCriteriaWithLLM(noticeText) {
  const systemPrompt = `당신은 정부지원사업 공고문 분석 전문가입니다.
공고문 텍스트에서 평가 기준 정보를 정확하게 추출하여 JSON 형식으로 반환합니다.
반드시 아래 JSON 형식만 반환하고, 다른 텍스트는 포함하지 마세요.`

  const userPrompt = `다음 공고문에서 평가 기준을 추출해주세요.

[공고문 텍스트]
${noticeText.slice(0, 3000)}

[출력 형식 - 반드시 이 JSON만 반환]
{
  "faceItems": [{"name": "항목명", "score": 점수}],
  "bonusItems": ["가점항목1", "가점항목2"],
  "quantitativeItems": ["정량지표1", "정량지표2"],
  "tiebreakerRule": "동점 처리 기준 설명",
  "totalScore": 합계점수
}

평가 항목이 없으면 빈 배열로 반환하세요. JSON 외 텍스트 절대 금지.`

  const content = await callLLM([
    { role: 'system', content: systemPrompt },
    { role: 'user',   content: userPrompt },
  ], { temperature: 0.1, maxTokens: 500 })

  try {
    return JSON.parse(content)
  } catch {
    return null
  }
}
```

---

## F-05: 사업계획서 작성 워크플로우 (3단계 — Slide 4~7 기준 전면 개편)

> **변경**: 기존 5단계 STEP stepper UI → 3단계 페이지 플로우로 대체  
> **삭제**: StepUpload, StepAnalysis, StepDiagnosis, StepInterview, StepReadiness (5개 파일)  
> **신규**: ApplyPrepPage, ApplyAnalysisPage, ApplyAiAssistPage (3개 파일)

### 4.5.0 3단계 워크플로우 플로우

```
[공고 상세 "사업계획서 작성" 클릭]
         ↓
[PAGE.APPLY_PREP — 자료 업로드]
  1. 공고문 자동 첨부 (완료 표시)
  2. 제출양식 업로드 (.docx/.pdf)
  3. 참고자료 다중 업로드
  [자료 분석 시작 → 충족도 검사] 버튼
         ↓
[PAGE.APPLY_ANALYSIS — 분석·충족도 (Slide 6)]
  좌: 섹션 트리 (완료/보완필요/미작성)
  중: 문서 미리보기 (실시간 업데이트)
  우: 자료 충족도 + 부족자료 요청
  [→ 부족도로 1차 초안 작성] 버튼
         ↓
[PAGE.APPLY_AI_ASSIST — AI 보완 도우미 (Slide 7)]
  좌: 섹션 트리 (동일)
  중: 초안 편집기 (실시간)
  우: AI 보완 도우미 채팅 패널
  [전체평가가기] → PAGE.EVALUATION
```

### 4.5.1 공고문 자동 첨부 구현

```javascript
// 공고 상세에서 "사업계획서 작성" 클릭 시 자동 처리
// src/features/pages/ApplyPrepPage.jsx

async function initializeApplySession(notice) {
  // 공고에 연결된 파일 자동 수집
  const autoFiles = []
  const attachments = parseAttachmentList(notice)

  for (const att of attachments) {
    try {
      // 공고 원문 URL에서 파일 다운로드 후 파싱
      const result = await parseFileFromUrl(att.url, att.name)
      autoFiles.push({
        key: 'notice',
        filename: att.name,
        type: att.type,
        parseStatus: 'done',
        parseText: result.text,
        source: 'auto',  // 자동 첨부 표시
      })
    } catch {
      // 다운로드 실패 시 메타정보만 표시
      autoFiles.push({ key: 'notice', filename: att.name, parseStatus: 'pending', source: 'auto' })
    }
  }

  // 공고 정보 자체도 컨텍스트로 포함
  autoFiles.push({
    key: 'notice',
    filename: `${notice.title}_공고정보.txt`,
    parseStatus: 'done',
    parseText: [notice.title, notice.target, notice.benefit, notice.content].join('\n'),
    source: 'auto',
  })

  return autoFiles
}
```

### 4.5.2 파일 파싱 API (변경 없음, 200MB 제한으로 상향)

### 4.5.2 백엔드 파일 파싱 API (Python FastAPI)

```python
# backend/routers/files.py

from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
import pdfplumber
import docx
import io

router = APIRouter(prefix="/api", tags=["files"])

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.hwp', '.xlsx', '.csv'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

@router.post("/parse-file")
async def parse_file(file: UploadFile = File(...)):
    """단일 파일 텍스트 추출"""
    # 확장자 검증
    filename = file.filename.lower()
    ext = '.' + filename.split('.')[-1] if '.' in filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(422, f"지원하지 않는 파일 형식: {ext}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "파일 크기가 50MB를 초과합니다")

    text = ""
    parse_success = True

    try:
        if ext == '.pdf':
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                text = "\n".join(
                    page.extract_text() or ""
                    for page in pdf.pages[:50]  # 최대 50페이지
                )
        elif ext == '.docx':
            doc = docx.Document(io.BytesIO(content))
            text = "\n".join(para.text for para in doc.paragraphs)
        elif ext in ('.xlsx', '.csv'):
            import pandas as pd
            if ext == '.xlsx':
                df = pd.read_excel(io.BytesIO(content))
            else:
                df = pd.read_csv(io.BytesIO(content))
            text = df.to_string()
        elif ext == '.hwp':
            # HWP 파싱 실패 처리
            parse_success = False
    except Exception as e:
        parse_success = False

    return {
        "filename": file.filename,
        "text": text[:10000],  # 최대 10,000자
        "char_count": len(text),
        "parse_success": parse_success,
        "error": None if parse_success else "파일 내용을 자동으로 읽지 못했습니다."
    }
```

### 4.5.3 작성 가능률 계산

```python
# backend/services/diagnosis.py

# 평가항목별 필요 정보 필드
REQUIRED_FIELDS_MAP = {
    "사업 필요성": [
        "current_defect_rate", "current_productivity", "pain_point", "market_size"
    ],
    "추진역량": [
        "company_summary", "sales", "employees", "existing_solutions", "certifications"
    ],
    "세부 추진계획": [
        "project_goal", "target_system", "timeline", "budget_plan", "responsible_team"
    ],
    "기대효과": [
        "expected_defect_rate", "expected_productivity", "employment_effect", "sales_effect"
    ],
    "예산계획": [
        "equipment_cost", "sw_cost", "consulting_cost", "own_funding_ratio"
    ],
}

def calculate_completeness(notice_text: str, uploaded_docs: dict[str, str], interview_answers: dict) -> dict:
    """
    returns: {
        "total": 64,
        "by_section": {"사업 필요성": 80, "추진역량": 70, ...},
        "missing_required": [...],
        "missing_optional": [...],
    }
    """
    all_text = " ".join([
        *uploaded_docs.values(),
        *[str(v) for v in interview_answers.values()],
    ]).lower()

    # 필드 존재 여부 체크 (키워드 기반)
    FIELD_KEYWORDS = {
        "current_defect_rate":   ["불량률", "ppm", "불량"],
        "current_productivity":  ["생산성", "uph", "생산량"],
        "pain_point":            ["문제점", "개선", "필요성"],
        "market_size":           ["시장", "규모"],
        "company_summary":       ["사업", "현황", "기업"],
        "sales":                 ["매출", "억원"],
        "employees":             ["직원", "근로자", "명"],
        "existing_solutions":    ["erp", "mes", "시스템"],
        "certifications":        ["인증", "특허"],
        "project_goal":          ["목표", "개선율"],
        "target_system":         ["도입", "ai", "비전", "자동화"],
        "timeline":              ["단계", "일정", "월"],
        "budget_plan":           ["예산", "사업비", "원"],
        "responsible_team":      ["담당", "팀", "부서"],
        "expected_defect_rate":  ["목표 불량률", "불량률.*감소"],
        "expected_productivity": ["생산성.*향상", "목표.*생산"],
        "employment_effect":     ["고용", "채용", "일자리"],
        "sales_effect":          ["매출.*증가", "수출"],
        "equipment_cost":        ["장비", "설비"],
        "sw_cost":               ["sw", "소프트웨어", "솔루션"],
        "consulting_cost":       ["컨설팅"],
        "own_funding_ratio":     ["자부담", "기업부담"],
    }

    section_scores = {}
    missing_required = []
    missing_optional = []

    for section, fields in REQUIRED_FIELDS_MAP.items():
        found = 0
        for field in fields:
            keywords = FIELD_KEYWORDS.get(field, [field])
            if any(kw in all_text for kw in keywords):
                found += 1
            else:
                if section in ["사업 필요성", "세부 추진계획", "기대효과"]:
                    missing_required.append({
                        "section": section,
                        "field": field,
                        "hint": f"{section} 작성에 '{field}' 정보가 필요합니다."
                    })
                else:
                    missing_optional.append({"section": section, "field": field})

        section_scores[section] = int(found / len(fields) * 100) if fields else 100

    total = int(sum(section_scores.values()) / len(section_scores)) if section_scores else 0

    return {
        "total": total,
        "by_section": section_scores,
        "missing_required": missing_required[:10],  # 최대 10개
        "missing_optional": missing_optional[:5],
    }
```

### 4.5.4 AI 인터뷰 질문 시퀀스 (고정 목록)

```javascript
// src/features/apply/interviewQuestions.js
// 이 목록은 고정이다. 추가/수정 시 PRD 개정 필요.

export const INTERVIEW_QUESTIONS = {
  current_defect_rate: {
    label: '현재 공정 불량률',
    question: '현재 공정의 불량률이 어떻게 되나요?',
    hint: '예: 불량률 3.2% 또는 320 PPM',
    type: 'text',
    placeholder: '예: 3.2% (또는 320 PPM)',
    storageKey: 'current_defect_rate',
  },
  project_goal: {
    label: '이번 사업 목표',
    question: '이번 사업으로 가장 개선하고 싶은 것은 무엇인가요?',
    hint: null,
    type: 'checkbox',
    options: ['생산성 향상', '불량률 감소', '원가 절감', '납기 단축', '매출 증가'],
    allowCustom: true,
    storageKey: 'project_goal',
  },
  target_system: {
    label: '도입할 시스템',
    question: '도입하려는 시스템이나 솔루션이 있나요?',
    hint: '예: AI 비전검사 시스템, MES 고도화, 스마트센서',
    type: 'text',
    placeholder: '예: AI 비전검사 + MES 연동',
    storageKey: 'target_system',
  },
  expected_defect_rate: {
    label: '목표 불량률',
    question: '목표 불량률이 얼마나 되나요?',
    hint: '현재값 → 목표값 형태로 입력해주세요',
    type: 'text',
    placeholder: '예: 3.2% → 1.5% (50% 감소)',
    storageKey: 'expected_defect_rate',
  },
  budget_plan: {
    label: '예산 계획',
    question: '총 사업비를 어떻게 배분할 계획인가요?',
    hint: '장비 / SW / 컨설팅 비용 구분',
    type: 'structured',
    fields: [
      { key: 'equipment', label: '장비/설비 비용', placeholder: '예: 5,000만원' },
      { key: 'software',  label: 'SW/솔루션 비용', placeholder: '예: 2,000만원' },
      { key: 'consulting',label: '컨설팅 비용',    placeholder: '예: 1,000만원' },
    ],
    storageKey: 'budget_plan',
  },
}
```

---

## F-06: 사업계획서 AI 초안 생성

### 4.6.1 LLM API 호출 함수 (완전 구현)

```javascript
// src/api/lmStudioApi.js

import { env } from '../config/env'

async function callLLM(messages, options = {}) {
  const {
    temperature = 0.7,
    maxTokens = 2000,
    model = 'local-model',
  } = options

  // OpenAI API 키가 있으면 OpenAI 우선 사용
  const useOpenAI = Boolean(env.openaiApiKey)
  const useAnthropic = Boolean(env.anthropicApiKey)

  if (useOpenAI) {
    const res = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${env.openaiApiKey}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        messages,
        temperature,
        max_tokens: maxTokens,
      }),
    })
    if (!res.ok) throw new Error(`OpenAI HTTP_${res.status}`)
    const data = await res.json()
    return data.choices[0].message.content
  }

  if (useAnthropic) {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': env.anthropicApiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: maxTokens,
        messages,
      }),
    })
    if (!res.ok) throw new Error(`Anthropic HTTP_${res.status}`)
    const data = await res.json()
    return data.content[0].text
  }

  // 기본: LM Studio
  const res = await fetch(`${env.lmStudioUrl}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, messages, temperature, max_tokens: maxTokens, stream: false }),
  })
  if (!res.ok) throw new Error(`LMStudio HTTP_${res.status}`)
  const data = await res.json()
  return data.choices[0].message.content
}

// ─── 공고 구조 분석 → 섹션 목록 추출 ─────────────────────────────────
export async function analyzeNoticeStructure(notice) {
  const systemPrompt = `당신은 정부지원사업 사업계획서 구조 분석 전문가입니다.
공고 정보를 분석하여 사업계획서에 필요한 섹션 목록을 JSON으로 반환합니다.
반드시 JSON 배열만 반환하고 다른 텍스트는 포함하지 마세요.`

  const userPrompt = `다음 공고를 분석하여 사업계획서 섹션 목록을 추출해주세요.

공고명: ${notice.title}
지원 대상: ${notice.target}
지원 내용: ${notice.benefit}
평가기준: ${JSON.stringify(notice.evaluationCriteria)}

[출력 형식 - JSON 배열만 반환]
[
  {"key": "1", "title": "사업 배경 및 필요성"},
  {"key": "2", "title": "추진 계획"},
  ...
]

최소 4개, 최대 7개 섹션으로 구성하세요.`

  const content = await callLLM([
    { role: 'system', content: systemPrompt },
    { role: 'user',   content: userPrompt },
  ], { temperature: 0.3, maxTokens: 500 })

  try {
    return JSON.parse(content)
  } catch {
    // 파싱 실패 시 기본 섹션 반환
    return [
      { key: '1', title: '사업 배경 및 필요성' },
      { key: '2', title: '신청 기업 현황' },
      { key: '3', title: '세부 추진 계획' },
      { key: '4', title: '기대 효과' },
      { key: '5', title: '예산 계획 개요' },
    ]
  }
}

// ─── 섹션 초안 생성 ───────────────────────────────────────────────────
export async function generateDraftSection({ section, notice, profileData, confirmedSections, interviewAnswers }) {
  const systemPrompt = `당신은 정부지원사업 사업계획서 전문 작성 보조 AI입니다.
기업 프로필, 공고 정보, 인터뷰 답변을 바탕으로 논리적이고 설득력 있는 내용을 작성합니다.
- 반드시 구체적인 수치와 근거를 포함하세요
- 평가기준의 각 항목을 반드시 반영하세요
- 문어체(~합니다, ~입니다)로 작성하세요
- 500~800자 분량으로 작성하세요`

  const confirmedText = confirmedSections.length > 0
    ? `\n[이전 확정 섹션]\n${confirmedSections.map((s) => `## ${s.key}. ${s.title}\n${s.content}`).join('\n\n')}`
    : ''

  const interviewText = Object.entries(interviewAnswers || {})
    .filter(([, v]) => v)
    .map(([k, v]) => `- ${k}: ${v}`)
    .join('\n')

  const userPrompt = `[공고 정보]
공고명: ${notice.title}
지원 대상: ${notice.target}
지원 혜택: ${notice.benefit}
평가기준: ${JSON.s