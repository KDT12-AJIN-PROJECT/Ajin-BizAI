# PRD-03: 정보 아키텍처 (Information Architecture)

> **문서 버전** 1.0 | **선행 문서** PRD-02 | **후행 문서** PRD-04  
> **목적** 화면 구조, 네비게이션, 라우팅의 완전한 명세

---

## 1. 전체 화면 트리

```
AJIN BizAI (SPA — 페이지 전환 = 조건부 렌더링)
│
├── [dashboard]         대시보드 ←── 앱 진입점
├── [notice_search]     공고 검색
├── [notice_preview]    공고 미리보기    ← TopNav 탭 (북마크 공고 일람)
├── [notice_detail]     공고 상세        ← selectedNotice 필요
├── [apply_prep]        사업계획서 작성   ← selectedNotice 필요
│   ├── [upload]        자료 업로드 (STEP 1)
│   ├── [analysis]      분석·충족도 검사 (STEP 2)
│   └── [ai_assist]     AI 보완 도우미   (STEP 3)
├── [evaluation]        평가             ← TopNav 탭 (AI 평가·보완)
├── [bookmarks]         북마크           ← Sidebar 메뉴
├── [notifications]     맞춤 알림        ← Sidebar 메뉴
├── [my_files]          내 자료실        ← Sidebar 메뉴 (신규)
└── [settings]          기업 프로필      ← TopNav 탭 & Sidebar
```

---

## 1-1. 네비게이션 구조 (Slide 2 디자인 기준)

### TopNav (상단 가로 탭)

```
AJIN BizAI | 대시보드 | 공고 검색 | 공고 미리보기 | 사업계획서 작성 | 평가 | 기업 프로필   ···
```

| 탭 | PAGE 상수 | 비고 |
|---|-----------|------|
| 대시보드 | `PAGE.DASHBOARD` | 기본 진입점 |
| 공고 검색 | `PAGE.NOTICE_SEARCH` | 필터·카드 목록 |
| 공고 미리보기 | `PAGE.NOTICE_PREVIEW` | 북마크 공고 요약 |
| 사업계획서 작성 | `PAGE.APPLY_PREP` | 업로드→분석→AI보완 |
| 평가 | `PAGE.EVALUATION` | AI 평가·보완 지원 |
| 기업 프로필 | `PAGE.SETTINGS` | 기업 정보 설정 |

### Left Sidebar (Slide 2 기준, 항상 표시)

```
┌─────────────────┐
│ AJIN BizAI      │  ← 로고 + "Government Funding Workflow"
│                 │
│ ▣ 대시보드       │  ← active 시 배경 강조
│ ○ 공고 검색      │
│ ○ 사업계획서     │
│   평가받기       │
│ ○ 북마크         │
│ ○ 맞춤 알림      │
│ ○ 내 자료실      │  ← 신규 (업로드한 참고자료 관리)
│ ○ 기업 설정      │
│                 │
│ ─────────────── │
│ [프로젝트 구간]   │  ← 진행 중 프로젝트 타임라인 요약
│ 강후 개발 Phase2 │
│ 2026 Q3~Q4      │
│ • 수행 보고서 Q3 │
│ • 변경 신청서 Q3 │
│ • 정산 보고서 Q4 │
│                 │
│ [🔔 출시 알림 받기]│  ← 하단 CTA 버튼
└─────────────────┘
```

**Sidebar 너비**: `w-64` (256px, 고정)  
**배경**: `bg-white border-r border-border`  
**Active 항목**: `bg-primary/10 text-primary font-medium rounded-md`

---

## 2. PAGE 상수 정의 (고정, 변경 금지)

```javascript
// src/constants/pages.js — 이 파일을 반드시 생성하고 아래 그대로 사용
export const PAGE = Object.freeze({
  DASHBOARD:        'dashboard',
  NOTICE_SEARCH:    'notice_search',
  NOTICE_PREVIEW:   'notice_preview',   // ← 신규: 공고 미리보기 탭
  NOTICE_DETAIL:    'notice_detail',
  APPLY_PREP:       'apply_prep',        // 사업계획서 작성 (업로드 단계)
  APPLY_ANALYSIS:   'apply_analysis',   // ← 신규: 분석·충족도 단계
  APPLY_AI_ASSIST:  'apply_ai_assist',  // ← 신규: AI 보완 도우미 단계
  EVALUATION:       'evaluation',        // ← 신규 (구 simulation → evaluation으로 명칭 변경)
  BOOKMARKS:        'bookmarks',
  NOTIFICATIONS:    'notifications',
  MY_FILES:         'my_files',          // ← 신규: 내 자료실
  SETTINGS:         'settings',
})

// 뒤로가기 맵 — 각 페이지에서 "← 뒤로" 클릭 시 이동할 페이지
export const BACK_PAGE = Object.freeze({
  [PAGE.NOTICE_DETAIL]:  PAGE.NOTICE_SEARCH,
  [PAGE.APPLY_PREP]:     PAGE.NOTICE_DETAIL,
  [PAGE.CHAT_DRAFT]:     PAGE.APPLY_PREP,
  [PAGE.QUICK_DRAFT]:    PAGE.NOTICE_DETAIL,
  [PAGE.SIMULATION]:     PAGE.CHAT_DRAFT,
  [PAGE.HISTORY]:        PAGE.DASHBOARD,
  [PAGE.BOOKMARKS]:      PAGE.DASHBOARD,
  [PAGE.NOTIFICATIONS]:  PAGE.DASHBOARD,
  [PAGE.SETTINGS]:       PAGE.DASHBOARD,
})

// TopNav에 표시할 페이지 제목
export const PAGE_TITLE = Object.freeze({
  [PAGE.DASHBOARD]:      'AJIN BizAI',
  [PAGE.NOTICE_SEARCH]:  '공고 검색',
  [PAGE.NOTICE_DETAIL]:  '공고 상세',
  [PAGE.APPLY_PREP]:     '신청 준비',
  [PAGE.CHAT_DRAFT]:     'AI 사업계획서 작성',
  [PAGE.QUICK_DRAFT]:    '빠른 초안',
  [PAGE.SIMULATION]:     '선정 평가 시뮬레이션',
  [PAGE.HISTORY]:        '신청 이력',
  [PAGE.BOOKMARKS]:      '북마크',
  [PAGE.NOTIFICATIONS]:  '맞춤 알림',
  [PAGE.SETTINGS]:       '기업 설정',
})
```

---

## 3. App.jsx 라우팅 구현 (완전한 코드)

```jsx
// src/App.jsx
import { useState, useCallback, useEffect } from 'react'
import { PAGE, BACK_PAGE } from './constants/pages'
import { AppContext } from './contexts/AppContext'
import { useAppState } from './hooks/useAppState'
import TopNav from './features/layout/TopNav'
import DashboardPage from './features/dashboard/DashboardPage'
import MainPage from './features/notices/components/NoticeList'        // 기존
import DetailPage from './features/notices/components/NoticeDetail'    // 기존
import ApplyPrepPage from './features/apply/ApplyPrepPage'              // 신규
import ChatDraftPage from './features/draft/ChatDraftPage'              // 기존
import QuickDraftPage from './features/draft/QuickDraftPage'            // 기존 (DraftPage → 이름 변경)
import SimulationPage from './features/simulation/SimulationPage'       // 신규
import HistoryPage from './features/history/HistoryPage'                // 신규
import BookmarksPage from './features/bookmarks/BookmarksPage'          // 신규
import NotificationPage from './features/pages/NotificationPage'        // 기존
import SettingsPage from './features/pages/SettingsPage'                // 기존

export default function App() {
  const [currentPage, setCurrentPage] = useState(PAGE.DASHBOARD)
  const appState = useAppState()  // 전역 상태 (PRD-07 참조)

  // 페이지 이동 함수 — 앱 전체에서 이 함수만 사용
  const navigate = useCallback((page, opts = {}) => {
    // opts.notice: 공고 상세·신청준비 진입 시 selectedNotice 설정
    if (opts.notice) appState.setSelectedNotice(opts.notice)
    setCurrentPage(page)
    window.scrollTo(0, 0)
  }, [appState])

  // 뒤로가기
  const goBack = useCallback(() => {
    const target = BACK_PAGE[currentPage] ?? PAGE.DASHBOARD
    setCurrentPage(target)
    window.scrollTo(0, 0)
  }, [currentPage])

  // ChatDraft·QuickDraft는 TopNav 숨김 (전체화면 모드)
  const hideTopNav = [PAGE.CHAT_DRAFT].includes(currentPage)

  return (
    <AppContext.Provider value={{ ...appState, navigate, goBack, currentPage }}>
      <div className="min-h-screen bg-background">
        {!hideTopNav && <TopNav />}
        <main className={hideTopNav ? '' : 'max-w-screen-xl mx-auto px-4 py-6'}>
          {currentPage === PAGE.DASHBOARD      && <DashboardPage />}
          {currentPage === PAGE.NOTICE_SEARCH  && <MainPage />}
          {currentPage === PAGE.NOTICE_DETAIL  && <DetailPage />}
          {currentPage === PAGE.APPLY_PREP     && <ApplyPrepPage />}
          {currentPage === PAGE.CHAT_DRAFT     && <ChatDraftPage />}
          {currentPage === PAGE.QUICK_DRAFT    && <QuickDraftPage />}
          {currentPage === PAGE.SIMULATION     && <SimulationPage />}
          {currentPage === PAGE.HISTORY        && <HistoryPage />}
          {currentPage === PAGE.BOOKMARKS      && <BookmarksPage />}
          {currentPage === PAGE.NOTIFICATIONS  && <NotificationPage />}
          {currentPage === PAGE.SETTINGS       && <SettingsPage />}
        </main>
      </div>
    </AppContext.Provider>
  )
}
```

---

## 4. TopNav 컴포넌트 명세

```jsx
// src/features/layout/TopNav.jsx
// props: 없음 (AppContext에서 currentPage, navigate 읽음)

// 네비게이션 항목 (순서 고정)
const NAV_ITEMS = [
  { page: PAGE.DASHBOARD,     label: '대시보드',  icon: LayoutDashboard },
  { page: PAGE.NOTICE_SEARCH, label: '공고 검색', icon: Search },
  { page: PAGE.HISTORY,       label: '신청 이력', icon: History },
  { page: PAGE.BOOKMARKS,     label: '북마크',    icon: Bookmark },
]

// 우측 액션 버튼 (순서 고정)
// 1. 기업 상황 버튼 → PAGE.SETTINGS 이동
// 2. 알림 벨 아이콘 (읽지 않은 알림 수 뱃지) → PAGE.NOTIFICATIONS 이동

// 높이: h-14 (56px)
// 배경: bg-background border-b border-border
// 로고: "AJIN BizAI" — font-bold text-primary
// 활성 탭: 텍스트 text-primary, 하단 border-b-2 border-primary
// 비활성 탭: text-muted-foreground hover:text-foreground
```

---

## 5. 각 화면의 진입 조건 및 가드

| 화면 | 진입 조건 | 조건 미충족 시 |
|------|---------|--------------|
| notice_detail | `selectedNotice !== null` | `navigate(PAGE.NOTICE_SEARCH)` |
| apply_prep | `selectedNotice !== null` | `navigate(PAGE.NOTICE_SEARCH)` |
| chat_draft | `selectedNotice !== null` | `navigate(PAGE.NOTICE_SEARCH)` |
| quick_draft | `selectedNotice !== null` | `navigate(PAGE.NOTICE_SEARCH)` |
| simulation | `draftSession.fullText.length > 100` | 빈 시뮬레이션 페이지 with "초안을 먼저 작성해주세요" |

```jsx
// DetailPage.jsx 최상단에 추가할 가드
const { selectedNotice, navigate } = useApp()
useEffect(() => {
  if (!selectedNotice) navigate(PAGE.NOTICE_SEARCH)
}, [selectedNotice])
if (!selectedNotice) return null
```

---

## 6. localStorage 키 목록 (전체)

```javascript
// src/constants/storageKeys.js
export const STORAGE_KEYS = Object.freeze({
  COMPANY_PROFILE:    'ajin_company_profile',      // CompanyProfile 객체
  BOOKMARKS:          'ajin_bookmarks',             // string[] (noticeId[])
  HISTORY:            'ajin_history',               // ApplicationRecord[]
  NOTICES_CACHE:      'ajin_notices_cache',         // { data: Notice[], timestamp: number }
  NOTIFICATIONS:      'ajin_notifications',         // Notification[]
  DRAFT_PREFIX:       'ajin_draft_',                // + noticeId → DraftSession
  CHECKLIST_PREFIX:   'ajin_checklist_',            // + noticeId → Record<string, boolean>
  SETTINGS:           'ajin_settings',              // { simThreshold, notiKeywords }
  APPLY_SESSION:      'ajin_apply_session',         // ApplySession (현재 진행 중)
})

// TTL 상수 (밀리초)
export const STORAGE_TTL = Object.freeze({
  NOTICES_CACHE:  60 * 60 * 1000,          // 1시간
  DRAFT:          30 * 24 * 60 * 60 * 1000, // 30일
  // 나머지는 TTL 없음 (영구)
})
```
