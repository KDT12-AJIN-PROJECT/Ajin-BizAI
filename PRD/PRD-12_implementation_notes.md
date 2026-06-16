# PRD-12: 구현 시 주의사항 (Implementation Notes for Claude Code)

> **문서 버전** 1.0 | **선행 문서** PRD-11  
> **목적** Claude Code 에이전트가 구현 중 잘못된 판단을 내리지 않도록 하는 결정 목록  
> **규칙** 이 문서의 지시를 따르지 않는 구현은 유효하지 않다.

---

## 절대 원칙 (10가지)

### 원칙 1: 기존 코드 최우선 활용

```
✅ 기존 파일의 함수·컴포넌트를 확장하라
❌ 기존 파일을 삭제하고 처음부터 다시 만들지 마라

구체적 예시:
- ChatDraftPage.jsx: 기존 코드에 EvalCriteriaChecklist 컴포넌트 추가
- normalizeNotice(): 기존 함수 본체를 PRD-04 코드로 교체 (파일명 유지)
- useNotices.js: 기존 파일을 PRD-07 §2 코드로 교체
```

### 원칙 2: 함수명·파일명·변수명 고정

```
PRD에 명시된 이름은 변경하지 마라.
예:
  ✅ fetchAllNotices()   ❌ fetchNotices(), getAllNotices()
  ✅ ajin_similarity     ❌ similarity, score, matchScore
  ✅ STORAGE_KEYS        ❌ KEYS, storageKeys, LOCAL_STORAGE_KEYS
  ✅ applySession        ❌ applicationSession, prepSession
```

### 원칙 3: LLM 기능은 선택적 강화

```
LLM 미연결 상태에서도 다음 기능은 반드시 동작해야 한다:
- 공고 수집·필터링·검색
- 적합도 계산 (Jaccard 유사도)
- 공고 상세 표시
- 서류 체크리스트
- 히스토리 관리
- 북마크

LLM이 없을 때 실패해도 되는 기능:
- AI 3줄 요약
- 평가기준 AI 파싱 (규칙 기반 폴백 사용)
- 초안 생성
- 점수 시뮬레이션
```

### 원칙 4: 파일 처리는 Python 백엔드 필수

```
React 단독으로 PDF 파싱 불가 → 반드시 backend/routers/files.py 구현
브라우저에서 pdfplumber 실행 불가 (Node.js 환경 아님)

파일 파싱 흐름:
React → fetch('/api/parse-file') → Express proxy → FastAPI → pdfplumber → 텍스트 반환
```

### 원칙 5: 기업 프로필은 항상 LLM 프롬프트에 포함

```javascript
// 모든 LLM 호출에서 기업 프로필을 포함시켜야 한다
// 누락 시 생성된 초안이 기업과 무관한 내용이 됨

// 잘못된 예
await generateDraftSection({ section, notice })

// 올바른 예
await generateDraftSection({ section, notice, profileData, confirmedSections, interviewAnswers })
```

### 원칙 6: AI 결과에 면책 문구 표시 (필수)

```
평가 시뮬레이션 결과 페이지에는 반드시 표시:
"⚠️ 예상 점수이며 실제 심사 결과와 다를 수 있습니다"

평가기준 AI 파싱 결과에는 반드시 표시:
"AI 추정 — 원문 확인 필수"

이 문구 없이 점수를 표시하는 것은 유효하지 않은 구현이다.
```

### 원칙 7: 동시수행 제한은 경고만 (차단 아님)

```
// 잘못된 구현 — 신청 자체를 막는 것
if (checkConcurrentLimit(history).hasConflict) {
  return <div>신청할 수 없습니다</div>  // ❌
}

// 올바른 구현 — 경고 배너만 표시, 진행 가능
{checkConcurrentLimit(history).hasConflict && (
  <Alert variant="warning">
    현재 수행 중인 사업이 있어 동시수행 제한이 있을 수 있습니다. 공고 원문을 확인하세요.
  </Alert>
)}
// 이후 계속 진행 가능
```

### 원칙 8: 에러 메시지는 반드시 한국어 상수 사용

```javascript
// 잘못된 구현 — 영어 에러 또는 하드코딩
setError('Connection failed')         // ❌
setError('LLM 연결 실패했습니다')      // ❌ (상수 미사용)

// 올바른 구현 — constants에서 가져옴
import { ERROR_MESSAGES } from '../constants/errorMessages'
setError(ERROR_MESSAGES.LLM_CONNECT_FAILED)  // ✅
```

### 원칙 9: shadcn/ui 컴포넌트 재사용 (신규 생성 금지)

```
src/components/ui/에 이미 있는 컴포넌트:
- Button, Card/CardContent/CardHeader/CardTitle
- Input, Label, Textarea, Separator
- Alert/AlertDescription, Badge

이것들을 재사용하라. 새 UI 컴포넌트 라이브러리 추가하지 마라.
```

### 원칙 10: 라우팅은 PAGE 상수만 사용

```javascript
// 잘못된 구현 — 문자열 직접 사용
setCurrentPage('notice_search')       // ❌
navigate('detail')                    // ❌

// 올바른 구현 — 상수 사용
import { PAGE } from '../constants/pages'
navigate(PAGE.NOTICE_SEARCH)          // ✅
navigate(PAGE.NOTICE_DETAIL, { notice: selectedNotice })  // ✅
```

---

## 자주 발생하는 실수 목록

| 실수 | 올바른 방법 |
|------|-----------|
| `localStorage.setItem(key, value)` 직접 호출 | `safeSetItem(key, value)` 사용 (용량 초과 처리 포함) |
| `new Date(dateString)` 사용 | `parseEndDate()` 함수 사용 (형식 다양성 처리) |
| `notice.id` 없는 상태로 렌더링 | `normalizeNotice()` 반드시 통과 후 사용 |
| LLM 응답 JSON.parse() 에러 미처리 | try-catch + null 반환 패턴 적용 |
| ChatDraftPage에서 최신 sections 참조 | `sectionsRef.current` 사용 (클로저 문제) |
| 파일 업로드 버튼 직접 클릭 처리 | `<input type="file">` + `onChange` 패턴 사용 |

---

## 구현 순서 (PRD-09와 연동)

```
Day 1~3  → PRD-03 §2,3 (상수, 라우팅) → PRD-07 §1 (AppContext)
Day 4~6  → PRD-04 §4.1 (공고 수집) → PRD-04 §4.2 (적합도)
Day 7~9  → PRD-04 §4.3 (필터링) → PRD-06 §Page 2 (MainPage 개선)
Day 10~12 → PRD-04 §4.4 (평가기준 파싱) → PRD-06 §Page 3 (DetailPage 개선)
Day 13~14 → PRD-06 §Page 1 (Dashboard) + PRD-06 §BookmarksPage
Day 15~17 → PRD-04 §4.5.2 (Python 파일 파싱) + PRD-05 §7 (FastAPI)
Day 18~28 → PRD-04 §4.5.3~5 (STEP 2~5) + PRD-06 §Page 4 (ApplyPrepPage)
Day 29~36 → PRD-04 §4.6 (초안) + PRD-04 §4.7 (시뮬레이션)
Day 37~42 → PRD-06 §Page 7 (HistoryPage) + PRD-04 §F-10 (알림)
Day 43~56 → 성능 최적화 + 테스트 + Docker 배포
```

---

## 파일 수정 vs 신규 생성 분류

### 기존 파일 수정 (교체/확장)
- `web-react/src/App.jsx` — 라우팅 전체 재구성
- `web-react/src/api/noticesApi.js` — fetchAllNotices 교체
- `web-react/src/api/lmStudioApi.js` — callLLM, generateDraftSection 교체
- `web-react/src/features/notices/utils/normalize.js` — 전체 교체
- `web-react/src/features/notices/utils/match.js` — 전체 교체
- `web-react/src/features/notices/utils/filtering.js` — 전체 교체
- `web-react/src/features/notices/components/NoticeDetail.jsx` — 섹션 추가
- `web-react/src/features/pages/SettingsPage.jsx` — 유지
- `web-react/src/features/pages/NotificationPage.jsx` — 알림 읽음 처리 추가

### 신규 생성 (없으면 생성)
- `web-react/src/constants/pages.js`
- `web-react/src/constants/storageKeys.js`
- `web-react/src/constants/errorMessages.js`
- `web-react/src/contexts/AppContext.jsx`
- `web-react/src/hooks/useAppState.js`
- `web-react/src/hooks/useAutoSave.js`
- `web-react/src/api/fileProcessApi.js`
- `web-react/src/features/dashboard/DashboardPage.jsx`
- `web-react/src/features/apply/ApplyPrepPage.jsx` (+ 5개 Step)
- `web-react/src/features/apply/interviewQuestions.js`
- `web-react/src/features/simulation/SimulationPage.jsx`
- `web-react/src/features/history/HistoryPage.jsx`
- `web-react/src/features/bookmarks/BookmarksPage.jsx`
- `web-react/src/features/notices/utils/evaluationParser.js`
- `web-react/src/services/storage.js`
- `web-react/src/services/notificationService.js`
- `backend/main.py`
- `backend/routers/files.py`
- `backend/routers/diagnosis.py`
- `backend/services/diagnosis.py`
- `backend/services/file_parser.py`
