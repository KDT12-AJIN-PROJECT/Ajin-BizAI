# PRD-06: 페이지별 구현 명세 (Page Implementation)

> **문서 버전** 1.0 | **선행 문서** PRD-05 | **후행 문서** PRD-07  
> **목적** 각 페이지 컴포넌트의 레이아웃·상태·핸들러 완전 명세

---

## 공통 레이아웃 규칙 (업데이트: Sidebar 추가)

- **전체 앱 구조**: `<div className="flex h-screen">` → Sidebar(w-64) + MainContent(flex-1)
- **MainContent**: `<div className="flex-1 flex flex-col overflow-hidden">`
  - TopNav (h-12, 상단 탭 바)
  - PageBody (`<main className="flex-1 overflow-y-auto p-6">`)
- **카드 컨테이너**: `<Card><CardContent className="px-5 py-4">…</CardContent></Card>`
- **섹션 제목**: `<CardTitle className="text-sm font-semibold">제목</CardTitle>`
- **최소 뷰포트**: 1280px (모바일 미지원)

---

## Page 1: DashboardPage (Slide 2 디자인 기준 전면 개편)

**파일**: `src/features/pages/DashboardPage.jsx` (기존 파일 전면 교체)  
**진입**: 앱 초기 접속, Sidebar "대시보드" 클릭

### 레이아웃

```
"오늘의 작업"
진행 중인 사업계획서, 마감 임박 공고, 최근 평가 결과를 한눈에

[4개 통계 카드] ─── grid-cols-4 gap-3
┌──────────┐ ┌──────────┐ ┌──────────────────┐ ┌──────────────────┐
│ 작성 중  │ │ 북마크   │ │ 마감 임박        │ │ 최근 평가        │
│    2     │ │    5     │ │       3          │ │      78          │
│ 편 진행중│ │ 관심 공고│ │ 7일 이내 ⚠       │ │ 점(스마트공장v3) │
└──────────┘ └──────────┘ └──────────────────┘ └──────────────────┘

[새 공고 검색 🔍]  ← 우측 상단 버튼 (outline, medium)

──────────── 2열 그리드 (grid-cols-[1fr_320px] gap-4) ────────────
좌열: 작성 중인 사업계획서               우열:
┌────────────────────────────────────┐   ┌────────────────────────┐
│ [TIPA] [챗봇 보완 중] [예상 67점]  │   │ ⚠ 마감 임박 공고        │
│ 2026년 스마트공장 구축 지원사업    │   │ 미래자동차 사업재편...D-4│
│ 약한 항목 3개 보완 중 · 저장 14:32 │   │ 뿌리산업 기술경쟁력 D-6 │
│ ████████████████░░░░ 72%  → 이어작성│  │ 소부장 양산성능 평가 D-7 │
├────────────────────────────────────┤   │ [모두 보기 →]           │
│ [KOSME] [자료 분석 중]             │   ├────────────────────────┤
│ 중소기업 R&D 역량강화 지원         │   │ 🏅 최근 평가 결과        │
│ 자료 충족도 검사 단계 · 저장 어제  │   │ 스마트공장 v3  78점 +11 │
│ ████░░░░░░░░░░░░░░░░ 35%  → 이어작성│  │ 커트라인 75점 · 통과     │
└────────────────────────────────────┘   │ R&D 역량강화 v2 67점 +8 │
                                         │ 커트라인 70점 미달       │
                                         └────────────────────────┘
```

### 컴포넌트 상태 및 데이터

```javascript
// src/features/pages/DashboardPage.jsx

import { useMemo } from 'react'
import { useApp } from '../../contexts/AppContext'
import { PAGE } from '../../constants/pages'

export default function DashboardPage() {
  const { navigate, notices, bookmarks, applyDrafts, evaluationHistory } = useApp()

  // 작성 중인 사업계획서 (status === 'drafting')
  const draftingItems = applyDrafts.filter(d => d.status === 'drafting')

  // 마감 임박 공고 (북마크 중 7일 이내)
  const urgentNotices = useMemo(() => {
    const now = Date.now()
    return notices
      .filter(n => bookmarks.includes(n.id) && n.date)
      .map(n => ({ ...n, daysLeft: Math.ceil((n.date.getTime() - now) / 86400000) }))
      .filter(n => n.daysLeft >= 0 && n.daysLeft <= 7)
      .sort((a, b) => a.daysLeft - b.daysLeft)
      .slice(0, 5)
  }, [notices, bookmarks])

  // 최근 평가 결과 (최신 2건)
  const recentEvals = evaluationHistory.slice(0, 2)

  // 통계 카드 값
  const stats = {
    draftCount:   draftingItems.length,
    bookmarkCount: bookmarks.length,
    urgentCount:  urgentNotices.length,
    latestScore:  recentEvals[0]?.score ?? null,
    latestTitle:  recentEvals[0]?.shortTitle ?? '-',
  }

  return (/* JSX 구현 — 아래 상세 참조 */)
}
```

### 통계 카드 명세 (4개 고정)

| 순서 | label | value | color | 아이콘 | 서브텍스트 |
|-----|-------|-------|-------|--------|---------|
| 1 | 작성 중 | `{draftCount}` | `text-primary` | FileText | "편 진행 중" |
| 2 | 북마크 | `{bookmarkCount}` | `text-amber-600` | Bookmark | "관심 공고" |
| 3 | 마감 임박 | `{urgentCount}` | `text-red-600` | AlertTriangle | "7일 이내" |
| 4 | 최근 평가 | `{latestScore ?? '-'}` | `text-emerald-600` | Award | `"점 (${latestTitle})"` |

### 마감 임박 공고 섹션

```jsx
// 우열 상단 카드
function UrgentNoticesCard({ items, onNavigate }) {
  const DDAY_COLOR = (d) =>
    d <= 3 ? 'text-red-600 bg-red-50'
    : d <= 7 ? 'text-amber-600 bg-amber-50'
    : 'text-muted-foreground bg-muted'

  return (
    <Card>
      <CardHeader className="pb-2 pt-4 px-5">
        <div className="flex items-center gap-1.5">
          <AlertTriangle className="w-4 h-4 text-red-500" aria-hidden="true" />
          <CardTitle className="text-sm">마감 임박 공고</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="px-5 pb-4 space-y-2">
        {items.length === 0 ? (
          <p className="text-xs text-muted-foreground py-2">7일 이내 마감 공고가 없습니다.</p>
        ) : items.map((notice) => (
          <button
            key={notice.id}
            type="button"
            onClick={() => onNavigate(PAGE.NOTICE_DETAIL, { notice })}
            className="w-full flex items-center justify-between text-left p-2 rounded-md hover:bg-muted transition-colors border-none bg-transparent cursor-pointer"
          >
            <span className="text-sm text-foreground truncate flex-1 mr-2">
              {notice.title}
            </span>
            <span className={`text-xs font-bold px-1.5 py-0.5 rounded shrink-0 ${DDAY_COLOR(notice.daysLeft)}`}>
              D-{notice.daysLeft}
            </span>
          </button>
        ))}
        <button
          type="button"
          onClick={() => onNavigate(PAGE.NOTICE_SEARCH)}
          className="text-xs text-primary hover:underline mt-1 bg-transparent border-none cursor-pointer"
        >
          모두 보기 →
        </button>
      </CardContent>
    </Card>
  )
}
```

### 최근 평가 결과 섹션

```jsx
// 우열 하단 카드
function RecentEvalCard({ items }) {
  return (
    <Card>
      <CardHeader className="pb-2 pt-4 px-5">
        <div className="flex items-center gap-1.5">
          <Award className="w-4 h-4 text-emerald-600" aria-hidden="true" />
          <CardTitle className="text-sm">최근 평가 결과</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="px-5 pb-4 space-y-3">
        {items.length === 0 ? (
          <p className="text-xs text-muted-foreground">아직 평가 결과가 없습니다.</p>
        ) : items.map((ev) => (
          <div key={ev.id}>
            <div className="flex items-center justify-between mb-0.5">
              <span className="text-sm font-medium text-foreground truncate max-w-[140px]">
                {ev.shortTitle}
              </span>
              <div className="flex items-center gap-1.5 shrink-0">
                <span className="text-sm font-bold text-foreground">{ev.score}점</span>
                <span className={`text-xs font-semibold ${ev.delta >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                  {ev.delta >= 0 ? '+' : ''}{ev.delta}
                </span>
              </div>
            </div>
            <p className={`text-xs ${ev.score >= ev.cutline ? 'text-emerald-600' : 'text-red-500'}`}>
              커트라인 {ev.cutline}점 {ev.score >= ev.cutline ? '· 통과' : '미달'}
            </p>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
```

### evaluationHistory 데이터 타입 (AppContext에 추가)

```typescript
// src/types/index.ts 에 추가
interface EvaluationHistoryItem {
  id: string
  noticeId: string
  shortTitle: string    // "스마트공장 v3" 등 표시용 짧은 이름
  score: number         // 예상 점수
  cutline: number       // 커트라인 추정
  delta: number         // 이전 대비 점수 변화 (+11, -3 등)
  evaluatedAt: string   // ISO 날짜
}
```

---

## Page 2: MainPage (공고 검색)

**파일**: `src/features/notices/components/NoticeList.jsx` (기존 파일 개선)

### 추가 구현 사항 (기존 코드 위에 추가)

```jsx
// NoticeCard에 추가할 요소 (기존 카드 하단)

// 1. 북마크 버튼 (카드 우상단)
<button
  aria-label={isBookmarked ? '북마크 제거' : '북마크 추가'}
  onClick={(e) => { e.stopPropagation(); toggleBookmark(notice.id) }}
  className="absolute top-3 right-3 p-1 rounded hover:bg-muted"
>
  <Bookmark
    className={`w-4 h-4 ${isBookmarked ? 'fill-primary text-primary' : 'text-muted-foreground'}`}
    aria-hidden="true"
  />
</button>

// 2. AI 3줄 요약 Expander (카드 최하단)
<Separator className="mt-2 mb-2" />
<button
  className="flex items-center gap-1 text-xs text-muted-foreground w-full"
  onClick={(e) => { e.stopPropagation(); setShowSummary(prev => !prev) }}
>
  <Sparkles className="w-3 h-3 text-primary" aria-hidden="true" />
  AI 3줄 요약
  <ChevronDown className={`w-3 h-3 ml-auto transition-transform ${showSummary ? 'rotate-180' : ''}`} />
</button>
{showSummary && (
  <div className="mt-2 text-xs text-muted-foreground leading-relaxed">
    {summary || <Loader2 className="w-3 h-3 animate-spin" />}
  </div>
)}
```

---

## Page 3: DetailPage (공고 상세) — 이미지 1→2 기준 전면 개편

**파일**: `src/features/notices/components/NoticeDetail.jsx`  
**핵심 변경**: LLM이 공고문을 읽어 각 섹션을 자동으로 채움. "제한사항" → "유의사항" 으로 명칭 변경.  
**임포트 추가**: `parseSupportAmount`, `parseCostBudget`, `parseSupportContentItems`, `parseLimitItems` (evaluationParser.js)

### 3-0. 전체 레이아웃 (이미지 2 기준)

```
[상단 버튼 바]
 ← 목록으로  |  [북마크]  [공고 원문]  [온라인 신청]  [빠른 조언]  [AI 대화형 작성]   D-N 마감

[타이틀 카드] (border-l-4 border-l-primary)
  공고명 (font-bold text-xl) ──────────────────────── [D-N 뱃지 우상단, 빨간색]
  소관기관 | 수행기관 | 지역: 전국 | 신청기간: YYYY-MM-DD ~ YYYY-MM-DD | 적합도: N.N%

──── 좌우 2열 그리드 (grid grid-cols-[1fr_380px] gap-4) ────

좌열                                     우열
────────────────────────                 ────────────────────────────────
① 지원 대상 카드                          ① 필수 비용 편성 안내  [AI 요약 버튼]
  지원대상: 텍스트                           · 회계정산 수수료
  신청자격: 텍스트                           · 교육비 N만원 필수 편성
                                             · 기술임치비 N만원 필수 편성
② 지원내용 카드 (체크마크 항목)              · 현물 편성 가능 범위
  ✅ 항목 제목
     상세 설명 (gray)                     ② 평가 기준 요약  [선정 가능성 판단 뱃지, green]
                                             서면평가 항목·배점: [태그들]
③ 지원혜택 카드 (2×N 그리드)               가점 항목: [태그들]
  [지원규모] [지원조건]                       정량 평가: [태그들]
  [지원한도] [비용]                           동점 처리: 텍스트
  [기간]
                                           ③ 유의사항 카드  ← ⚠️ "제한사항" → "유의사항" 변경
④ 유의사항 카드 (좌열 하단)                  🔴 신청 제외 대상 경고 (bg-red-50)
  ⚠️ 동시 수행 제한  (amber bg)              원문 공고 확인 안내
  ⚠️ 참여제한 제재   (amber bg)
  ⚠️ 중복 지원 금지  (amber bg)

──── 전체 너비 ────
[공고문/첨부파일 다운로드]  파일명 + [다운로드] 버튼
[공고문 미리보기]  빈 상태 UI + [전체보기 →] 링크
```

### 3-0-1. 명칭 변경 규칙 (반드시 준수)

```javascript
// ❌ 절대 사용 금지
"제한사항"
"제한 사항"

// ✅ 올바른 명칭
"유의사항"

// 적용 위치: 카드 제목, aria-label, 함수명 주석 등 모두
```

### 3-1. 지원내용 체크마크 카드 (신규)

```jsx
// 좌열 2번째 카드: 지원내용 (체크마크 항목 리스트)
function SupportContentCard({ benefit }) {
  const items = parseSupportContentItems(benefit)
  if (items.length === 0) return (
    <Card>
      <CardHeader className="pb-2 pt-4 px-5">
        <CardTitle className="text-sm">지원내용</CardTitle>
      </CardHeader>
      <CardContent className="px-5 pb-4">
        <p className="text-sm text-muted-foreground leading-relaxed">{benefit || '-'}</p>
      </CardContent>
    </Card>
  )
  return (
    <Card>
      <CardHeader className="pb-2 pt-4 px-5">
        <CardTitle className="text-sm">지원내용</CardTitle>
      </CardHeader>
      <CardContent className="px-5 pb-4 space-y-2">
        {items.map((item, i) => (
          <div key={i} className="flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 text-primary mt-0.5 shrink-0" aria-hidden="true" />
            <div>
              <p className="text-sm font-medium text-foreground">{item.label}</p>
              {item.detail && (
                <p className="text-xs text-muted-foreground mt-0.5">{item.detail}</p>
              )}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
```

### 3-2. 지원혜택 그리드 카드 (신규)

```jsx
// 좌열 3번째 카드: 지원혜택 (2×N 그리드)
function SupportAmountCard({ benefit }) {
  const amt = parseSupportAmount(benefit)
  // 파싱 실패 시 텍스트 폴백
  if (!amt || (!amt.maxRatio && !amt.maxAmount)) {
    return (
      <Card>
        <CardHeader className="pb-2 pt-4 px-5"><CardTitle className="text-sm">지원혜택</CardTitle></CardHeader>
        <CardContent className="px-5 pb-4">
          <p className="text-sm text-muted-foreground">{benefit || '-'}</p>
        </CardContent>
      </Card>
    )
  }
  const ITEMS = [
    { label: '지원규모', value: amt.maxRatio },
    { label: '지원조건', value: amt.condition },
    { label: '지원한도', value: amt.maxAmount },
    { label: '비용',     value: amt.selfRatio },
    { label: '기간',     value: amt.period },
  ].filter((i) => i.value)

  return (
    <Card>
      <CardHeader className="pb-2 pt-4 px-5"><CardTitle className="text-sm">지원혜택</CardTitle></CardHeader>
      <CardContent className="px-5 pb-4">
        <div className="grid grid-cols-2 gap-2">
          {ITEMS.map((item) => (
            <div key={item.label} className="bg-muted/40 rounded-md px-3 py-2">
              <p className="text-xs text-muted-foreground mb-0.5">{item.label}</p>
              <p className="text-sm font-semibold text-foreground">{item.value}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
```

### 3-3. 지원제한사항 경고 카드 (신규)

```jsx
// 좌열 4번째 카드: 지원제한사항 (오렌지 경고 스타일)
function SupportLimitCard({ limit }) {
  const items = parseLimitItems(limit)
  return (
    <Card>
      <CardHeader className="pb-2 pt-4 px-5"><CardTitle className="text-sm">지원제한사항</CardTitle></CardHeader>
      <CardContent className="px-5 pb-4 space-y-2">
        {items.length > 0 ? items.map((item) => (
          <div key={item.title} className="flex items-start gap-2 p-2.5 rounded-md bg-amber-50 border border-amber-200">
            <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" aria-hidden="true" />
            <div>
              <p className="text-sm font-medium text-amber-900">{item.title}</p>
              <p className="text-xs text-amber-700 mt-0.5">{item.desc}</p>
            </div>
          </div>
        )) : (
          <p className="text-sm text-muted-foreground">{limit || '원본 공고를 참조하세요.'}</p>
        )}
      </CardContent>
    </Card>
  )
}
```

### 3-4. 필수 비용 편성 안내 카드 (신규, 우열 1번째)

```jsx
// 우열 1번째 카드: 필수 비용 편성 안내 (AI 요약 버튼 포함)
function CostBudgetCard({ notice, noticeText }) {
  const [items, setItems] = useState(() => parseCostBudget(noticeText))
  const [isLoading, setIsLoading] = useState(false)

  const handleAISummary = async () => {
    setIsLoading(true)
    try {
      // LLM에 필수 비용 편성 안내 항목 요약 요청
      const prompt = `다음 공고에서 "필수 비용 편성" 항목(교육비, 기술임치비, 회계정산 수수료, 현물 편성 등)만 추출하여 불릿 목록으로 반환하세요.\n${noticeText?.slice(0, 2000)}`
      const result = await callLLM([{ role: 'user', content: prompt }], { temperature: 0.1, maxTokens: 300 })
      const parsed = result.split('\n').filter((l) => l.trim().startsWith('•') || l.trim().startsWith('-'))
        .map((l) => l.replace(/^[•\-]\s*/, '').trim())
      if (parsed.length > 0) setItems(parsed)
    } catch { /* 실패 시 기존 items 유지 */ }
    finally { setIsLoading(false) }
  }

  return (
    <Card>
      <CardHeader className="pb-2 pt-4 px-5">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">필수 비용 편성 안내</CardTitle>
          <Button size="sm" variant="ghost" className="h-6 px-2 text-xs gap-1" onClick={handleAISummary} disabled={isLoading}>
            {isLoading
              ? <Loader2 className="w-3 h-3 animate-spin" aria-hidden="true" />
              : <Sparkles className="w-3 h-3 text-primary" aria-hidden="true" />
            }
            AI 요약
          </Button>
        </div>
      </CardHeader>
      <CardContent className="px-5 pb-4 space-y-2">
        {items.length > 0 ? items.map((item, i) => (
          <div key={i} className="flex items-start gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" aria-hidden="true" />
            <p className="text-sm text-foreground">{item}</p>
          </div>
        )) : (
          <p className="text-xs text-muted-foreground">공고 원문에서 필수 비용 편성 정보를 확인하세요.</p>
        )}
      </CardContent>
    </Card>
  )
}
```

### 3-5. 제한사항 카드 — 신청 제외 대상 (우열 하단)

```jsx
// 우열 하단: 제한사항 (붉은 배경)
function ExclusionCard({ limitText }) {
  if (!limitText) return null
  return (
    <Card>
      <CardHeader className="pb-2 pt-4 px-5"><CardTitle className="text-sm">제한사항</CardTitle></CardHeader>
      <CardContent className="px-5 pb-4 space-y-2">
        <div className="flex items-start gap-2 p-3 rounded-md bg-red-50 border border-red-200">
          <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" aria-hidden="true" />
          <p className="text-sm text-red-800">신청 제외 대상은 원본 공고를 참조하세요.</p>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">
          원공고의 신청 자격 및 제한 사항을 반드시 확인하시기 바랍니다.
        </p>
      </CardContent>
    </Card>
  )
}
```

### 3-6. 공고문 미리보기 (빈 상태 UI + 전체보기)

```jsx
// 공고문 미리보기 섹션
function NoticePreviewSection({ notice }) {
  const [isExpanded, setIsExpanded] = useState(false)
  return (
    <Card>
      <CardHeader className="pb-2 pt-4 px-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Eye className="w-4 h-4 text-muted-foreground" aria-hidden="true" />
            <CardTitle className="text-sm">공고문 미리보기</CardTitle>
          </div>
          {notice.url && (
            <Button variant="ghost" size="sm" className="text-xs h-6 gap-1" asChild>
              <a href={notice.url} target="_blank" rel="noreferrer">
                전체보기 <ChevronRight className="w-3 h-3" aria-hidden="true" />
              </a>
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="px-5 pb-4">
        {/* 공고 원문 URL이 있어도 CORS로 iframe 직접 임베드 불가 → 빈 상태 UI */}
        <div className="flex flex-col items-center justify-center py-8 text-muted-foreground rounded-md bg-muted/30 border border-dashed border-border">
          <FileText className="w-8 h-8 mb-2 opacity-40" aria-hidden="true" />
          <p className="text-sm font-medium">공고문 미리보기 영역</p>
          <p className="text-xs mt-1">공고 원문 연동 시 표시됩니다</p>
          {notice.url && (
            <Button variant="outline" size="sm" className="mt-3 gap-1" asChild>
              <a href={notice.url} target="_blank" rel="noreferrer">
                <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" /> 원문 새 탭에서 보기
              </a>
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
```

### 3-7. 평가 기준 요약 카드 — 뱃지 텍스트 수정

```jsx
// 평가 기준 요약 카드 (기존 코드에 추가)
// 위치: 우측 열 상단
// ⚠️ 뱃지 텍스트: "선정 가능성 판단" (green variant) — "AI 추정 — 원문 확인 필수" 아님

function EvaluationCriteriaCard({ criteria, isLoading }) {
  if (isLoading) return <Card><CardContent className="p-4"><Loader2 className="w-4 h-4 animate-spin" /></CardContent></Card>
  if (!criteria) return (
    <Card>
      <CardHeader className="pb-2 pt-4 px-5">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">평가 기준 요약</CardTitle>
          <Badge variant="outline" className="text-xs">AI 추정</Badge>
        </div>
      </CardHeader>
      <CardContent className="px-5 pb-4">
        <p className="text-xs text-muted-foreground">평가 기준 정보가 없습니다. 공고 원문을 확인하세요.</p>
      </CardContent>
    </Card>
  )
  return (
    <Card>
      <CardHeader className="pb-2 pt-4 px-5">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">평가 기준 요약</CardTitle>
          {/* ✅ 수정: "AI 추정 — 원문 확인 필수" → "선정 가능성 판단" (green variant) */}
          <Badge variant="success" className="text-xs">선정 가능성 판단</Badge>
        </div>
      </CardHeader>
      <CardContent className="px-5 pb-4 space-y-3">
        {/* 서면평가 항목 */}
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1.5">서면평가 항목·배점</p>
          <div className="flex flex-wrap gap-1.5">
            {criteria.faceItems.map((item) => (
              <Badge key={item.name} variant="blue" className="text-xs">
                {item.name} {item.score}점
              </Badge>
            ))}
          </div>
        </div>
        {/* 가점 항목 */}
        {criteria.bonusItems.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1.5">가점 항목</p>
            <div className="flex flex-wrap gap-1.5">
              {criteria.bonusItems.map((item) => (
                <Badge key={item} variant="success" className="text-xs">{item}</Badge>
              ))}
            </div>
          </div>
        )}
        {/* 정량 평가 */}
        {criteria.quantitativeItems.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1.5">정량 평가 기준</p>
            <div className="flex flex-wrap gap-1.5">
              {criteria.quantitativeItems.map((item) => (
                <Badge key={item} variant="outline" className="text-xs">{item}</Badge>
              ))}
            </div>
          </div>
        )}
        {/* 동점 처리 */}
        {criteria.tiebreakerRule && (
          <p className="text-xs text-muted-foreground">
            <span className="font-medium">동점 처리: </span>{criteria.tiebreakerRule}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

// 제출 서류 체크리스트 (기존 코드에 추가)
function DocChecklist({ noticeId, items }) {
  const storageKey = `${STORAGE_KEYS.CHECKLIST_PREFIX}${noticeId}`
  const [checked, setChecked] = useState(() => {
    try { return JSON.parse(localStorage.getItem(storageKey) || '{}') }
    catch { return {} }
  })
  const toggle = (name) => {
    const next = { ...checked, [name]: !checked[name] }
    setChecked(next)
    localStorage.setItem(storageKey, JSON.stringify(next))
  }
  return (
    <Card>
      <CardHeader className="pb-2 pt-4 px-5">
        <CardTitle className="text-sm">제출 서류 체크리스트</CardTitle>
      </CardHeader>
      <CardContent className="px-5 pb-4 space-y-2">
        {items.map((item) => (
          <label key={item.name} className="flex items-start gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={!!checked[item.name]}
              onChange={() => toggle(item.name)}
              className="mt-0.5 accent-primary"
              aria-label={item.name}
            />
            <span className="text-sm">
              {item.name}
              {item.required && <span className="text-destructive ml-1">*</span>}
              {item.validityPeriod && (
                <span className="text-xs text-muted-foreground ml-1">({item.validityPeriod})</span>
              )}
            </span>
          </label>
        ))}
      </CardContent>
    </Card>
  )
}
```

---

## Page 4~8: 제출 서류 작성 — 5단계 워크플로우

> **중요**: 5단계 STEPPER 구조는 유지한다. 각 단계의 UI·기능을 스크린샷 기준으로 개선한다.  
> **파일**: `src/features/apply/` 하위 파일들  
> **상단 공통 헤더** (5단계 전체 공통):

```
← 상세로          제출 서류 작성
                 자동 저장됨 · 다른 화면 이동해도 작성 내용 유지

[STEP 1 자료업로드] ─── [STEP 2 자료검사] ─── [STEP 3 초안작성] ─── [STEP 4 전략검토] ─── [STEP 5 완료&제출]
   ✅(완료)                ✅(완료)               🔵(현재)               ○                    ○
```

**STEP 아이콘 규칙**:
- 완료: 초록색 체크 원 (`bg-green-500 text-white`)
- 현재: 파란색 원 + 해당 아이콘 (`bg-primary text-white`)  
- 미완료: 회색 원 + 해당 아이콘 (`bg-muted text-muted-foreground`)

---

## Page 4-1: STEP 1 — 자료 업로드 (이미지 14→12/13 기준)

**파일**: `src/features/apply/StepUpload.jsx`  
**이전 UI**: 6개 단순 슬롯 → **새 UI**: 3섹션 구조 (공고문/제출양식/참고자료)

### 레이아웃

```
자료 업로드
공고문 · 제출양식 · 참고자료 3종을 업로드하세요.
자료가 부족해도 1차 초안은 만들 수 있습니다.

┌─ 1. 공고문  [자동 첨부 뱃지, green] ────────────────────── [확인] ─┐
│ ✅ 공고에서 자동으로 가져왔습니다.                                   │
│ 4개 파일 (공고문 / 운영지침 / 신청양식 / 평가기준표)                  │
│ (green 배경 bg-green-50, border-green-200)                          │
└───────────────────────────────────────────────────────────────────┘

┌─ 2. 제출양식 (사업계획서 양식)  [선택 뱃지, gray] ─────────────────┐
│                                                                     │
│  📄 기관별 별첨 양식이 따로 있다면 업로드하세요 (.docx, .hwp, .pdf) │
│     업로드 아이콘 + 드래그앤드롭 영역                                │
│  [+ 파일 선택]                                                       │
└───────────────────────────────────────────────────────────────────┘

┌─ 3. 참고자료  ──────────────────── [아직 업로드된 파일이 없습니다] ─┐
│ 회사소개서 / 신청서 양식 / 사업계획서 양식 / 이전 신청서/사업계획서   │
│ / 재무/참고 자료 / 기타 참고자료                                     │
│                                                                     │
│  📤 파일을 드래그하거나 클릭해서 한번에 업로드                        │
│     PDF · DOCX · HWP · XLSX · 이미지 · 파일당 최대 200MB · 다중 선택│
│  [+ 파일 선택]  (dark blue button, bg-primary)                      │
│                                                                     │
│ (업로드 후) 업로드된 파일 목록:                                       │
│  📄 회사소개서_2024.pdf   1.4 MB  04-08 14:01  ✓ 분석 완료  [👁][×] │
│  📄 사업보고서_2024.pdf   5.2 MB  04-08 14:01  ⟳ 긴 문서 청킹       │
│  ...                                                                │
└───────────────────────────────────────────────────────────────────┘

ℹ 업로드한 자료는 자동 분류되어 사업계획서 항목별로 매핑됩니다.
  긴 문서(예: 사업보고서 287페이지)는 페이지·섹션 단위로 참고합니다.
  자료가 부족해도 1차 초안 작성은 가능합니다.

[← 공고로 돌아가기]          STEP 1 / 5          [다음 →]
```

### 섹션 1 구현 (공고문 자동 첨부)

```jsx
// 섹션 1: 공고문 — 항상 자동 첨부 상태로 표시
function NoticeAutoSection({ notice }) {
  const attachments = parseAttachmentList(notice)
  const fileCount = Math.max(attachments.length, 4) // 최소 4개로 표시

  return (
    <div className="rounded-lg border border-green-200 bg-green-50 p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-foreground">1. 공고문</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">
            자동 첨부
          </span>
        </div>
        <button className="text-xs text-primary hover:underline bg-transparent border-none cursor-pointer">
          확인
        </button>
      </div>
      <div className="flex items-center gap-2 text-sm text-green-700">
        <CheckCircle2 className="w-4 h-4 shrink-0" aria-hidden="true" />
        공고에서 자동으로 가져왔습니다.
        {fileCount}개 파일 (공고문 / 운영지침 / 신청양식 / 평가기준표)
      </div>
    </div>
  )
}
```

### 섹션 3 파일 목록 상태 표시

```javascript
// 파일 분석 상태 타입
const FILE_STATUS = {
  uploading:  { label: '업로드 중...',  icon: Loader2,    color: 'text-muted-foreground', animate: true },
  analyzing:  { label: '분석 중',       icon: Loader2,    color: 'text-blue-600',         animate: true },
  done:       { label: '분석 완료',     icon: CheckCircle2, color: 'text-green-600',       animate: false },
  chunking:   { label: '긴 문서 청킹',  icon: Scissors,   color: 'text-amber-600',        animate: false },
  error:      { label: '오류',          icon: AlertCircle, color: 'text-red-500',          animate: false },
}
```

### 하단 버튼

```jsx
// 하단 고정 버튼 바
<div className="flex items-center justify-between pt-4 border-t">
  <Button variant="ghost" size="sm" onClick={onBack}>
    ← 공고로 돌아가기
  </Button>
  <span className="text-xs text-muted-foreground">STEP 1 / 5</span>
  <Button onClick={onNext}>
    다음 →
  </Button>
</div>
```

---

## Page 4-2: STEP 2 — 자료 검사 (이미지 6→9 기준)

**파일**: `src/features/apply/StepDataCheck.jsx`  
**핵심**: LLM이 업로드 자료를 분석해 서류 충족 여부 판단. 초안 작성 버튼을 시각적으로 강조.

### 레이아웃

```
자료 검사
업로드된 자료의 충족 여부를 확인합니다.

┌──── 통계 카드 행 (4개, grid-cols-4) ─────────────────────────────┐
│  전체 항목      준비 완료      검토 필요      업로드 파일          │
│    4개           0개            4개            0개                │
│                (green)        (amber)        (primary)            │
└───────────────────────────────────────────────────────────────────┘

준비도 0%  ← 진행바 (전체 너비, h-2, gray→green)

┌──── 서류 체크리스트 ──────────────────────────────────────────────┐
│                                                                   │
│  🟡 회사소개서  [필수 뱃지, red]                      미업로드    │
│  🟡 신청서 양식  [필수 뱃지, red]                     미업로드    │
│  🟡 사업계획서 양식                                   미업로드    │
│  🟡 재무/참고 자료                                    미업로드    │
│                                                                   │
│  ⚠️ 필수 서류 회사소개서, 신청서 양식가 없습니다.                   │
│     다음 단계로 넘어가도 AI가 프로필 정보로 대체 작성하지만         │
│     품질이 낮을 수 있습니다.                                       │
│     (amber border, amber bg, rounded-md, p-3)                     │
└───────────────────────────────────────────────────────────────────┘

┌──── 추가하면 좋을 자료 ────────────────────────────────────────────┐
│                                                                    │
│ · 기업명 — 신청 기업 현황에 필요요. 관련 자료 업로드 시 자동완성 가능. │
│ · 대표자 — 신청 기업 현황에 필요요. 관련 자료 업로드 시 자동완성 가능. │
│ · 주요 사업 및 제품 — 사업 개요에 필요요.                           │
│ · 연간 매출액 — 재무 현황에 필요요.                                 │
│ (각 행: blue dot + text, bg-blue-50 border-blue-100)               │
└───────────────────────────────────────────────────────────────────┘

[← 이전]    STEP 2 / 5    [다음 →]  +  [✦ 초안 작성 바로 시작] ← 강조 버튼
```

### 초안 작성 버튼 강조 구현

```jsx
// 하단 버튼 바 — 초안 작성 버튼을 눈에 띄게
<div className="flex items-center justify-between pt-4 border-t">
  <Button variant="ghost" size="sm" onClick={onPrev}>← 이전</Button>
  <span className="text-xs text-muted-foreground">STEP 2 / 5</span>
  <div className="flex items-center gap-2">
    <Button variant="outline" onClick={onNext}>다음 →</Button>
    {/* 시각적으로 강조된 초안 작성 버튼 */}
    <Button
      className="gap-1.5 bg-primary shadow-lg shadow-primary/25 hover:shadow-primary/40 transition-shadow"
      onClick={onGoToDraft}
    >
      <Sparkles className="w-4 h-4" aria-hidden="true" />
      초안 작성 바로 시작
    </Button>
  </div>
</div>
```

### 서류 체크리스트 항목 상태

```javascript
// 서류 상태별 스타일
const DOC_STATUS = {
  uploaded_ok:   { icon: CheckCircle2, color: 'text-green-500', label: '분석 완료' },
  uploaded_warn: { icon: AlertTriangle, color: 'text-amber-500', label: '검토 필요' },
  missing:       { icon: Circle,       color: 'text-amber-400', label: '미업로드' },
}

// 서류 목록 (순서 고정)
const DOC_CHECKLIST = [
  { key: 'company_intro', label: '회사소개서',     required: true },
  { key: 'application',   label: '신청서 양식',    required: true },
  { key: 'biz_plan',      label: '사업계획서 양식', required: false },
  { key: 'financial',     label: '재무/참고 자료',  required: false },
]
```

---

## Page 4-3: STEP 3 — 초안 작성 (이미지 7→10 기준)

**파일**: `src/features/apply/StepDraft.jsx`  
**핵심**: 좌측 섹션 목록 + 중앙 에디터(직접 수정 가능) + 우측 AI 챗봇. LLM이 섹션별 초안 생성.

### 레이아웃 (3패널, 전체 너비)

```
초안 작성                                                [✦ 전체 자동 작성] ← 우상단 강조 버튼
AI가 LLM을 통해 제출 서류를 항목별로 작성합니다.
0 / 5 항목 완성

┌─────────────────────────────────────────────────────────────────────────┐
│ 좌패널 (w-72)                                                           │
│                                                                         │
│  ○ 신청 기업 개요                                    [AI 작성]  ∨      │
│    ┌─────────────────────────────────────────────────────────────────┐ │
│    │ AI 작성 버튼을 눌러 "신청 기업 개요" 항목을 자동 작성하거나      │ │
│    │ 직접 입력하세요.                                                 │ │
│    │ (textarea, h-48, font-mono text-sm, 직접 수정 가능)             │ │
│    └─────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ○ 사업 참여 목적 및 필요성                          [AI 작성]  ∨      │
│  ○ 세부 추진 계획                                    [AI 작성]  ∨      │
│  ○ 기대 효과                                         [AI 작성]  ∨      │
│  ○ 예산 계획 개요                                    [AI 작성]  ∨      │
│                                                                         │
│ 우패널 (w-80)                                                           │
│                                                                         │
│  AI 검토 챗봇                                                           │
│  현재 편집 중: 신청 기업 개요                                            │
│                                                                         │
│  [AI]: 작성된 초안을 검토해 드리겠습니다.                               │
│        수정이 필요한 부분이나 질문이 있으면 말씀해 주세요.               │
│                                                                         │
│  ─────────────────────────────                                          │
│  수정 요청 또는 질문 입력... (Enter 전송)             [전송 ↑]           │
└─────────────────────────────────────────────────────────────────────────┘

[← 이전]     STEP 3 / 5     [다음 →]
```

### 섹션별 AI 작성 구현

```jsx
// StepDraft.jsx 핵심 구조
const DRAFT_SECTIONS = [
  { key: 'company_overview',  label: '신청 기업 개요' },
  { key: 'purpose',           label: '사업 참여 목적 및 필요성' },
  { key: 'plan',              label: '세부 추진 계획' },
  { key: 'expected_result',   label: '기대 효과' },
  { key: 'budget',            label: '예산 계획 개요' },
]

// 각 섹션 상태 (pending | generating | done)
const [sectionStates, setSectionStates] = useState(
  Object.fromEntries(DRAFT_SECTIONS.map(s => [s.key, { status: 'pending', content: '' }]))
)

// AI 작성 버튼 핸들러
async function handleAiWrite(sectionKey) {
  setSectionStates(prev => ({ ...prev, [sectionKey]: { ...prev[sectionKey], status: 'generating' } }))
  try {
    const content = await generateDraftSection({
      section: DRAFT_SECTIONS.find(s => s.key === sectionKey),
      notice: selectedNotice,
      profileData: companyProfile,
      uploadedTexts: applySession.parsedTexts,
    })
    setSectionStates(prev => ({ ...prev, [sectionKey]: { status: 'done', content } }))
  } catch (err) {
    setSectionStates(prev => ({ ...prev, [sectionKey]: { status: 'pending', content: '' } }))
    setError(ERROR_MESSAGES.LLM_CONNECT_FAILED)
  }
}

// 전체 자동 작성
async function handleWriteAll() {
  for (const section of DRAFT_SECTIONS) {
    await handleAiWrite(section.key)
  }
}
```

### 에디터 — 직접 수정 가능

```jsx
// 섹션별 아코디언 에디터
function SectionEditor({ section, state, onChange, onAiWrite }) {
  const [isOpen, setIsOpen] = useState(true)

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-4 py-3 bg-muted/30">
        <div className="flex items-center gap-2">
          {state.status === 'done'
            ? <CheckCircle2 className="w-4 h-4 text-green-500" aria-hidden="true" />
            : <Circle className="w-4 h-4 text-muted-foreground" aria-hidden="true" />
          }
          <span className="text-sm font-medium">{section.label}</span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs gap-1"
            disabled={state.status === 'generating'}
            onClick={() => onAiWrite(section.key)}
          >
            {state.status === 'generating'
              ? <><Loader2 className="w-3 h-3 animate-spin" /> 작성 중...</>
              : <><Sparkles className="w-3 h-3 text-primary" /> AI 작성</>
            }
          </Button>
          <ChevronDown
            className={`w-4 h-4 cursor-pointer transition-transform ${isOpen ? 'rotate-180' : ''}`}
            onClick={() => setIsOpen(p => !p)}
          />
        </div>
      </div>

      {/* 에디터 (직접 수정 가능) */}
      {isOpen && (
        <textarea
          className="w-full p-4 text-sm font-mono leading-relaxed resize-none min-h-[180px]
                     border-0 focus:outline-none focus:ring-0 bg-white"
          placeholder={`AI 작성 버튼을 눌러 "${section.label}" 항목을 자동 작성하거나 직접 입력하세요.`}
          value={state.content}
          onChange={e => onChange(section.key, e.target.value)}
        />
      )}
    </div>
  )
}
```

### AI 챗봇 패널

```jsx
// 우측 AI 챗봇 패널 — 현재 열린 섹션과 연동
function DraftChatPanel({ currentSection, messages, onSend }) {
  const [input, setInput] = useState('')

  return (
    <div className="flex flex-col h-full border-l border-border">
      {/* 헤더 */}
      <div className="px-4 py-3 border-b">
        <p className="text-xs font-semibold">AI 검토 챗봇</p>
        <p className="text-xs text-muted-foreground">현재 편집 중: {currentSection.label}</p>
      </div>

      {/* 메시지 목록 */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.map(msg => (
          <div key={msg.id} className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`text-xs leading-relaxed p-2.5 rounded-lg max-w-[85%]
              ${msg.role === 'user' ? 'bg-primary text-white' : 'bg-muted text-foreground'}`}>
              {msg.content}
            </div>
          </div>
        ))}
      </div>

      {/* 입력창 */}
      <div className="p-3 border-t flex gap-2">
        <input
          type="text"
          className="flex-1 text-xs border rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-primary"
          placeholder="수정 요청 또는 질문 입력... (Enter 전송)"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(input); setInput('') } }}
        />
        <Button size="icon" className="h-8 w-8 shrink-0" onClick={() => { onSend(input); setInput('') }}>
          <Send className="w-3.5 h-3.5" aria-hidden="true" />
        </Button>
      </div>
    </div>
  )
}
```

---

## Page 4-4: STEP 4 — 전략 검토 (이미지 8→11 기준)

**파일**: `src/features/apply/StepStrategy.jsx`  
**핵심**: "AI 평가·보완 작업 지휘실" 스타일. 평가항목별 카드로 문제점·AI보완안·필요자료를 동시에 표시.

### 레이아웃

```
전략 검토
작성된 초안을 검토하고 AI 챗봇으로 수정 요청을 할 수 있습니다.

[섹션 탭 (수평 스크롤)]
[신청 기업 개요]  [사업 참여 목적 및 필요성]  [세부 추진 계획]  [기대 효과]  [예산 계획 개요]
   ↑ 현재 선택 (bg-primary text-white)

┌───────────────────────────────┬──────────────────────────────────────┐
│ 좌: 텍스트 에디터 (flex-1)    │ 우: AI 검토 챗봇 (w-80)              │
│                               │                                      │
│ 내용을 직접 수정하거나         │ AI 검토 챗봇                         │
│ 오른쪽 챗봇에게 수정 요청하세요│ 현재 편집 중: 신청 기업 개요         │
│                               │                                      │
│ [텍스트 에디터]               │ [AI]: 작성된 초안을 검토해 드리겠습니다│
│ (직접 수정 가능,              │       수정이 필요한 부분이나 질문이    │
│  font-mono, leading-relaxed,  │       있으면 말씀해 주세요.           │
│  min-h-[400px])               │                                      │
│                               │                                      │
│                               │ ──────────────────────────────────── │
│                               │ 수정 요청 또는 질문 입력... [Enter↑] │
└───────────────────────────────┴──────────────────────────────────────┘

[← 이전]     STEP 4 / 5     [다음 →]
```

### 구현 코드

```jsx
// StepStrategy.jsx
export default function StepStrategy({ sections, onUpdateSection, onPrev, onNext }) {
  const [activeTab, setActiveTab] = useState(sections[0]?.key ?? '')
  const [messages, setMessages] = useState([{
    id: 'init', role: 'assistant',
    content: '작성된 초안을 검토해 드리겠습니다. 수정이 필요한 부분이나 질문이 있으면 말씀해 주세요.',
  }])

  const currentSection = sections.find(s => s.key === activeTab)
  const currentContent = currentSection?.content ?? ''

  async function handleChatSend(userMessage) {
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', content: userMessage }])
    const reply = await reviseDraftSection({
      section: currentSection,
      currentContent,
      feedback: userMessage,
      notice: selectedNotice,
    })
    setMessages(prev => [...prev, { id: Date.now() + 1, role: 'assistant', content: reply }])
    // 채팅 답변을 에디터에 반영
    onUpdateSection(activeTab, reply)
  }

  return (
    <div className="space-y-4">
      {/* 섹션 탭 */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {sections.map(s => (
          <button
            key={s.key}
            type="button"
            onClick={() => setActiveTab(s.key)}
            className={`px-4 py-2 text-sm rounded-md whitespace-nowrap transition-colors border-none cursor-pointer
              ${activeTab === s.key
                ? 'bg-primary text-white font-medium'
                : 'bg-muted text-foreground hover:bg-muted/70'}`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* 2열 패널 */}
      <div className="grid grid-cols-[1fr_320px] gap-4 min-h-[500px]">
        {/* 좌: 텍스트 에디터 */}
        <div className="border border-border rounded-lg overflow-hidden flex flex-col">
          <div className="px-4 py-2 bg-muted/30 border-b text-xs text-muted-foreground">
            내용을 직접 수정하거나 오른쪽 챗봇에게 수정 요청하세요.
          </div>
          <textarea
            className="flex-1 p-4 text-sm font-mono leading-relaxed resize-none focus:outline-none"
            value={currentContent}
            onChange={e => onUpdateSection(activeTab, e.target.value)}
          />
        </div>

        {/* 우: AI 챗봇 */}
        <DraftChatPanel
          currentSection={currentSection}
          messages={messages}
          onSend={handleChatSend}
        />
      </div>

      {/* 하단 버튼 */}
      <div className="flex items-center justify-between pt-4 border-t">
        <Button variant="ghost" size="sm" onClick={onPrev}>← 이전</Button>
        <span className="text-xs text-muted-foreground">STEP 4 / 5</span>
        <Button onClick={onNext}>다음 →</Button>
      </div>
    </div>
  )
}
```

---

## Page 4-5: STEP 5 — 완료 & 제출

**파일**: `src/features/apply/StepComplete.jsx`  
**내용**: 최종 초안 다운로드 + 온라인 신청 링크 + 이력 저장

```jsx
// 완료 화면 구조
<div className="space-y-6 text-center py-8">
  <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto">
    <CheckCircle2 className="w-8 h-8 text-green-600" aria-hidden="true" />
  </div>
  <h2 className="text-xl font-bold">제출 서류 작성 완료!</h2>
  <p className="text-sm text-muted-foreground">
    작성된 초안을 다운로드하거나 공고 신청 페이지로 이동하세요.
  </p>

  <div className="flex gap-3 justify-center">
    <Button variant="outline" onClick={handleDownload}>
      <Download className="w-4 h-4" /> 초안 다운로드 (.txt)
    </Button>
    {notice.rceptEngnHmpgUrl && (
      <Button asChild>
        <a href={notice.rceptEngnHmpgUrl} target="_blank" rel="noreferrer">
          <ExternalLink className="w-4 h-4" /> 온라인 신청하기
        </a>
      </Button>
    )}
  </div>

  {/* 이력 저장 */}
  <p className="text-xs text-muted-foreground">
    신청 이력에 자동 저장됩니다.
  </p>
</div>
```

---

## Page 5~8: 기타 페이지 (변경 없음)

- `BookmarksPage`, `NotificationPage`, `SettingsPage`: 기존 명세 유지
- `EvaluationPage` (`PAGE.EVALUATION`): PRD-04 F-07 명세 참조
- `HistoryPage`: PRD-04 F-08 명세 참조
