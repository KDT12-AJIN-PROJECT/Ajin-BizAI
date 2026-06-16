# PRD-08: 비기능 요구사항 (Non-Functional Requirements)

> **문서 버전** 1.0 | **선행 문서** PRD-07 | **후행 문서** PRD-09

---

## 1. 성능 요구사항

| 지표 | 목표값 | 측정 방법 | 미달 시 조치 |
|------|--------|---------|------------|
| 초기 로딩 LCP | < 3초 | Lighthouse 측정 | 코드 스플리팅, 이미지 lazy |
| 공고 목록 로딩 | < 5초 | `Date.now()` 차이 | 캐시 TTL 적용 |
| AI 적합도 계산 | < 2초 (1,000건) | `console.time()` | Web Worker 분리 |
| LLM 초안 생성 | 섹션당 < 30초 | fetch 타임아웃 | 타임아웃 30,000ms |
| PDF 파싱 | < 10초 (50MB) | 백엔드 응답 시간 | 비동기 처리 |

### 성능 구현 코드

```javascript
// LLM 요청 타임아웃 래퍼
async function callLLMWithTimeout(messages, options = {}, timeoutMs = 30000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await callLLM(messages, { ...options, signal: controller.signal })
  } finally {
    clearTimeout(timer)
  }
}

// 번들 최적화 (vite.config.js manualChunks)
manualChunks: {
  vendor: ['react', 'react-dom'],
  ui: ['lucide-react'],
}
```

---

## 2. 보안 요구사항

### 2.1 파일 업로드 검증 (React 클라이언트)

```javascript
// src/features/apply/StepUpload.jsx 내 검증 함수

const ALLOWED_EXTENSIONS = new Set(['.pdf', '.docx', '.hwp', '.xlsx', '.csv'])
const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  // 50MB
const MAX_FILE_COUNT = 10

export function validateFile(file) {
  const name = file.name.toLowerCase()
  const ext = '.' + name.split('.').pop()

  if (!ALLOWED_EXTENSIONS.has(ext)) {
    return { valid: false, error: `지원하지 않는 파일 형식입니다: ${ext}. PDF, DOCX, HWP, XLSX, CSV만 가능합니다.` }
  }
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return { valid: false, error: `파일 크기가 50MB를 초과합니다: ${(file.size / 1024 / 1024).toFixed(1)}MB` }
  }
  return { valid: true, error: null }
}
```

### 2.2 파일 업로드 검증 (Python 백엔드)

```python
# backend/routers/files.py
ALLOWED_MIME_TYPES = {
    'application/pdf': ['.pdf'],
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    'application/haansofthwp': ['.hwp'],
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    'text/csv': ['.csv'],
}
```

### 2.3 API 키 보호
- **절대 금지**: `VITE_` prefix 환경변수에 공공 API 키 직접 저장 (브라우저 노출)
- **올바른 방법**: Express `server.js`에서 `process.env.BIZ_KEY`로 읽어 프록시 시 주입
- XSS: React 기본 이스케이핑 활용, `dangerouslySetInnerHTML` 사용 금지

---

## 3. 에러 처리 명세

### 에러 메시지 한국어 상수 (고정)

```javascript
// src/constants/errorMessages.js — 변경 금지
export const ERROR_MESSAGES = Object.freeze({
  API_FETCH_FAILED:      '공고 데이터를 불러오지 못했습니다. 잠시 후 새로고침해주세요.',
  API_ALL_FAILED:        '외부 공고 API 연결에 실패하여 샘플 데이터를 표시합니다. API 키 설정을 확인하세요.',
  LLM_CONNECT_FAILED:    'AI 서버에 연결할 수 없습니다. LM Studio가 실행 중인지 확인하세요.',
  LLM_TIMEOUT:           'AI 응답 시간이 초과되었습니다. 다시 시도해주세요.',
  LLM_PARSE_FAILED:      'AI 응답을 처리하지 못했습니다. 다시 시도해주세요.',
  FILE_TOO_LARGE:        '파일 크기가 50MB를 초과합니다. 더 작은 파일을 사용해주세요.',
  FILE_TYPE_INVALID:     '지원하지 않는 파일 형식입니다. PDF, DOCX, HWP, XLSX, CSV만 가능합니다.',
  FILE_PARSE_FAILED:     '파일 내용을 자동으로 읽지 못했습니다. 텍스트를 직접 붙여넣어주세요.',
  DRAFT_SAVE_FAILED:     '초안 저장에 실패했습니다. 브라우저 저장공간을 확인해주세요.',
  SIMULATION_FAILED:     '점수 시뮬레이션에 실패했습니다. 초안 내용이 너무 짧지 않은지 확인하세요.',
  NETWORK_OFFLINE:       '인터넷 연결을 확인해주세요.',
  UNKNOWN:               '알 수 없는 오류가 발생했습니다. 페이지를 새로고침해주세요.',
})
```

### UI 처리 기준

| 상황 | UI 컴포넌트 | 위치 |
|------|-----------|------|
| API 일부 실패 | `<Alert variant="destructive">` | 공고 목록 상단 |
| API 전체 실패 | 주황색 상단 배너 | 앱 전체 상단 |
| LLM 연결 실패 | 인라인 에러 메시지 + 재시도 버튼 | 채팅 패널 |
| 파일 파싱 실패 | 파일 행 노란 경고 아이콘 | StepUpload |
| 네트워크 오프라인 | 상단 회색 배너 | 앱 전체 상단 |

---

## 4. 접근성 (WCAG 2.1 AA)

```jsx
// 올바른 접근성 구현 패턴

// 1. 아이콘 버튼 — aria-label 필수
<button aria-label="북마크 추가"><Bookmark aria-hidden="true" /></button>

// 2. 진행바
<div role="progressbar" aria-valuenow={72} aria-valuemin={0} aria-valuemax={100} aria-label="작성 완료율" />

// 3. 로딩 상태
<div role="status" aria-live="polite">
  {isLoading ? '공고를 불러오는 중...' : ''}
</div>

// 4. 에러 메시지
<div role="alert" aria-live="assertive">{errorMessage}</div>
```

---

## 5. 브라우저 지원

| 브라우저 | 지원 버전 | 비고 |
|---------|---------|------|
| Chrome | 120+ | ✅ 주요 대상 |
| Edge | 120+ | ✅ 지원 |
| Firefox | 121+ | ✅ 지원 |
| Safari | 17+ | ✅ 지원 |
| IE | 모든 버전 | ❌ 미지원 |
| 모바일 Chrome/Safari | - | ❌ MVP 미지원 |

모바일 접속 시: `"AJIN BizAI는 데스크톱 전용 서비스입니다. PC에서 접속해주세요."` 안내

---

## 6. 국제화 (i18n)

- **언어**: 한국어 전용 (v1.0)
- **인코딩**: UTF-8 (BOM 없음)
- **날짜 포맷**: `YYYY-MM-DD` (ISO 8601) — `date.js` 유틸 사용
- **숫자 포맷**: `N.toLocaleString('ko-KR')` — "1,264건"
- **시간대**: `Asia/Seoul` (KST, UTC+9)
