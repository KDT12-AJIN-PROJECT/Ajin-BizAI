# PRD-10: 테스트 명세 (Test Specifications)

> **문서 버전** 1.0 | **선행 문서** PRD-09 | **후행 문서** PRD-11  
> **테스트 도구** Vitest (단위/통합), Playwright (E2E), pytest (Python 백엔드)

---

## 1. 테스트 원칙

- 모든 유틸 함수(`utils/`)는 단위 테스트 필수
- API 호출 함수는 Mock 처리하여 테스트
- 에러 시나리오 테스트 비율 ≥ 30%
- 커버리지 목표: **80%** (`vitest --coverage`)

---

## 2. 단위 테스트

### 2.1 match.test.js

```javascript
// src/features/notices/utils/match.test.js
import { describe, test, expect } from 'vitest'
import { tokenize, similarityScore, buildNoticeCorpus, buildProfileCorpus } from './match'

describe('tokenize', () => {
  test('한국어 토큰 분리', () => {
    const result = tokenize('자동차 부품 스마트공장')
    expect(result).toContain('자동차')
    expect(result).toContain('부품')
    expect(result).toContain('스마트공장')
  })

  test('특수문자 제거', () => {
    const result = tokenize('AI·DX·자동화!')
    expect(result).not.toContain('!')
    expect(result).not.toContain('·')
  })

  test('빈 문자열 → 빈 배열', () => {
    expect(tokenize('')).toEqual([])
    expect(tokenize(null)).toEqual([])
  })

  test('1글자 토큰 제외', () => {
    const result = tokenize('a bc def')
    expect(result).not.toContain('a')
    expect(result).toContain('bc')
  })
})

describe('similarityScore', () => {
  test('자동차 부품 프로필 vs 스마트공장 공고 — 유사도 양수', () => {
    const profile = '자동차 부품 스마트공장 DX 제조혁신'
    const corpus  = '스마트공장 구축 제조기업 DX 전환 자동차'
    expect(similarityScore(profile, corpus)).toBeGreaterThan(0.1)
  })

  test('관련 없는 텍스트 — 유사도 낮음', () => {
    const profile = '자동차 부품 제조'
    const corpus  = '농업 관개 수리시설 개선'
    expect(similarityScore(profile, corpus)).toBeLessThan(0.05)
  })

  test('빈 프로필 → 0 반환', () => {
    expect(similarityScore('', '스마트공장')).toBe(0)
  })

  test('빈 공고 → 0 반환', () => {
    expect(similarityScore('자동차 부품', '')).toBe(0)
  })

  test('동일 텍스트 → 1 반환', () => {
    expect(similarityScore('테스트 텍스트', '테스트 텍스트')).toBe(1)
  })
})
```

### 2.2 normalize.test.js

```javascript
// src/features/notices/utils/normalize.test.js
import { describe, test, expect } from 'vitest'
import { normalizeNotice, dedupeNotices, parseAttachmentList } from './normalize'

const MOCK_RAW_BIZINFO = {
  pblancNm: '2026 스마트공장 구축 지원사업',
  reqstBeginEndDe: '2026-04-01 ~ 2026-05-10',
  trgetNm: '중소/중견 제조기업',
  bsnsSumryCn: '자동화 및 품질고도화 지원',
  suptCn: '장비도입 비용 지원',
  areaNm: '전국',
  pblancUrl: 'https://www.bizinfo.go.kr/test',
}

describe('normalizeNotice', () => {
  test('기업마당 응답 정규화', () => {
    const notice = normalizeNotice(MOCK_RAW_BIZINFO, '기업마당')
    expect(notice.title).toBe('2026 스마트공장 구축 지원사업')
    expect(notice.origin).toBe('기업마당')
    expect(notice.date).toBeInstanceOf(Date)
    expect(notice.region).toBe('전국')
    expect(notice.id).toBeTruthy()
  })

  test('날짜 파싱 — YYYY-MM-DD ~ YYYY-MM-DD 형식', () => {
    const notice = normalizeNotice(MOCK_RAW_BIZINFO, '기업마당')
    expect(notice.date?.getFullYear()).toBe(2026)
    expect(notice.date?.getMonth()).toBe(4) // 5월 = index 4
    expect(notice.date?.getDate()).toBe(10)
  })

  test('날짜 파싱 — 날짜 없는 경우 null', () => {
    const notice = normalizeNotice({ pblancNm: '테스트' }, '기업마당')
    expect(notice.date).toBeNull()
  })

  test('ID 생성 — 같은 제목+날짜는 같은 ID', () => {
    const n1 = normalizeNotice(MOCK_RAW_BIZINFO, '기업마당')
    const n2 = normalizeNotice(MOCK_RAW_BIZINFO, '중기부')
    expect(n1.id).toBe(n2.id)
  })
})

describe('dedupeNotices', () => {
  test('중복 제거', () => {
    const notices = [
      normalizeNotice(MOCK_RAW_BIZINFO, '기업마당'),
      normalizeNotice(MOCK_RAW_BIZINFO, '중기부'), // 같은 ID
    ]
    expect(dedupeNotices(notices)).toHaveLength(1)
  })

  test('다른 공고는 유지', () => {
    const n1 = normalizeNotice(MOCK_RAW_BIZINFO, '기업마당')
    const n2 = normalizeNotice({ ...MOCK_RAW_BIZINFO, pblancNm: '다른 공고' }, '기업마당')
    expect(dedupeNotices([n1, n2])).toHaveLength(2)
  })
})
```

### 2.3 filtering.test.js

```javascript
// src/features/notices/utils/filtering.test.js
import { describe, test, expect } from 'vitest'
import { filterNotices, sortNotices, paginateNotices } from './filtering'
import { normalizeNotice } from './normalize'

const makeNotice = (overrides) => normalizeNotice({
  pblancNm: overrides.title || '테스트 공고',
  areaNm: overrides.region || '전국',
  trgetNm: overrides.target || '중소기업',
  reqstBeginEndDe: overrides.period || '2026-04-01 ~ 2026-06-30',
  bsnsSumryCn: overrides.content || '',
  ...overrides.raw,
}, '기업마당')

describe('filterNotices', () => {
  const notices = [
    { ...makeNotice({ title: '스마트공장 A' }), ajin_similarity: 0.08 },
    { ...makeNotice({ title: '바이오 B' }), ajin_similarity: 0.01 },
    { ...makeNotice({ title: '스마트공장 C', region: '경남' }), ajin_similarity: 0.05 },
  ]

  test('적합도 임계값 0.05 필터링', () => {
    const filters = { matchMode: 'AI적합도', threshold: 0.05, searchTitle: '',
      selectedKeywords: [], selectedRegions: [], selectedSizes: [] }
    const result = filterNotices(notices, filters)
    expect(result).toHaveLength(2) // A(0.08), C(0.05)
  })

  test('제목 검색', () => {
    const filters = { matchMode: 'AI적합도', threshold: 0, searchTitle: '스마트공장',
      selectedKeywords: [], selectedRegions: [], selectedSizes: [] }
    const result = filterNotices(notices, filters)
    expect(result).toHaveLength(2)
    expect(result.every(n => n.title.includes('스마트공장'))).toBe(true)
  })

  test('지역 필터 — 전국 공고는 모든 지역에 매칭', () => {
    const filters = { matchMode: 'AI적합도', threshold: 0, searchTitle: '',
      selectedKeywords: [], selectedRegions: ['경남'], selectedSizes: [] }
    const result = filterNotices(notices, filters)
    expect(result.length).toBeGreaterThanOrEqual(1)
  })
})

describe('sortNotices', () => {
  const notices = [
    { ...makeNotice({}), ajin_similarity: 0.03, date: new Date('2026-05-01') },
    { ...makeNotice({}), ajin_similarity: 0.08, date: new Date('2026-04-10') },
    { ...makeNotice({}), ajin_similarity: 0.01, date: new Date('2026-06-30') },
  ]

  test('적합도순 정렬', () => {
    const sorted = sortNotices(notices, '적합도순')
    expect(sorted[0].ajin_similarity).toBe(0.08)
    expect(sorted[2].ajin_similarity).toBe(0.01)
  })

  test('마감일 가까운 순', () => {
    const sorted = sortNotices(notices, '마감일 가까운 순')
    expect(sorted[0].date.getMonth()).toBe(3) // 4월
  })
})

describe('paginateNotices', () => {
  const notices = Array.from({ length: 25 }, (_, i) => makeNotice({ title: `공고 ${i}` }))

  test('1페이지 9건', () => {
    const { items, totalPages } = paginateNotices(notices, 1, 9)
    expect(items).toHaveLength(9)
    expect(totalPages).toBe(3)
  })

  test('마지막 페이지 7건', () => {
    const { items } = paginateNotices(notices, 3, 9)
    expect(items).toHaveLength(7)
  })

  test('범위 초과 페이지 → 마지막 페이지로 보정', () => {
    const { page } = paginateNotices(notices, 99, 9)
    expect(page).toBe(3)
  })
})
```

---

## 3. 통합 테스트 체크리스트 (수동)

| # | 테스트 케이스 | 전제 조건 | 기대 결과 | 실제 결과 |
|---|------------|---------|---------|---------|
| T01 | 공고 API 전체 실패 → Mock 표시 | 모든 API URL 잘못 설정 | 샘플 공고 3건 + 주황 경고 배너 | ☐ |
| T02 | 적합도 임계값 10% → 필터링 | 공고 100건 로드 후 | 고적합 공고만 표시 (건수 감소) | ☐ |
| T03 | PDF 업로드 → 텍스트 추출 | 실제 공고문 PDF | parse_success=true, text 길이 > 100 | ☐ |
| T04 | HWP 업로드 → 폴백 안내 | HWP 파일 업로드 | 노란 경고 + "텍스트 직접 입력" 버튼 | ☐ |
| T05 | LLM 미연결 → 빠른 초안 시도 | LM_STUDIO_URL 차단 | 에러 메시지 + [재시도] [빠른초안 전환] 버튼 | ☐ |
| T06 | 히스토리 2건 수행 중 → 공고 상세 | 2건 isOngoing=true 저장 | 경고 배너 "현재 2건 수행 중" 표시 | ☐ |
| T07 | 북마크 저장 → 새로고침 후 유지 | 공고 북마크 후 F5 | 북마크 유지 | ☐ |
| T08 | AI 인터뷰 5개 답변 → 가능률 90%+ | STEP 4 완료 | readinessScore >= 90 | ☐ |
| T09 | ChatDraft 3섹션 confirmed → 다운로드 | 3섹션 확인 완료 | TXT 파일 다운로드 성공 | ☐ |
| T10 | 점수 시뮬레이션 → JSON 파싱 성공 | 초안 500자 이상 | totalEstimated, bySection 표시 | ☐ |

---

## 4. Python 백엔드 테스트

```python
# backend/tests/test_files.py
from fastapi.testclient import TestClient
from main import app
import io

client = TestClient(app)

def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_parse_pdf_success():
    # 간단한 PDF 바이트 생성
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "테스트 공고문 내용입니다.")
    c.save()
    buf.seek(0)

    res = client.post("/api/parse-file", files={"file": ("test.pdf", buf, "application/pdf")})
    assert res.status_code == 200
    data = res.json()
    assert data["parse_success"] is True
    assert "테스트" in data["text"]

def test_parse_invalid_extension():
    res = client.post("/api/parse-file",
        files={"file": ("test.exe", b"binary", "application/octet-stream")})
    assert res.status_code == 422

def test_parse_oversized_file():
    big_content = b"x" * (51 * 1024 * 1024)  # 51MB
    res = client.post("/api/parse-file",
        files={"file": ("big.pdf", big_content, "application/pdf")})
    assert res.status_code == 413
```

---

## 5. Vitest 설정

```javascript
// vite.config.js에 추가
test: {
  globals: true,
  environment: 'jsdom',
  setupFiles: ['./src/test/setup.js'],
  coverage: {
    provider: 'v8',
    reporter: ['text', 'lcov'],
    exclude: ['node_modules/', 'src/components/ui/'],
    thresholds: { lines: 80, functions: 80, branches: 70 },
  },
},
```

```javascript
// src/test/setup.js
import '@testing-library/jest-dom'
// localStorage mock
const localStorageMock = (() => {
  let store = {}
  return {
    getItem: (key) => store[key] || null,
    setItem: (key, value) => { store[key] = String(value) },
    removeItem: (key) => { delete store[key] },
    clear: () => { store = {} },
  }
})()
Object.defineProperty(window, 'localStorage', { value: localStorageMock })
```
