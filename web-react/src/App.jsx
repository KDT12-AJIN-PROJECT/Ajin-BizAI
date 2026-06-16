import { useCallback, useEffect, useMemo, useState } from 'react'
import { Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { cn } from './lib/utils'
import { DEFAULT_AJIN_PROFILE, DEFAULT_PROFILE_DATA, KEYWORD_GROUPS, REGION_OPTIONS, SIZE_OPTIONS } from './config/defaults'
import Sidebar from './features/layout/Sidebar'
import TopNav from './features/layout/TopNav'
import { useBookmarks } from './features/notices/hooks/useBookmarks'
import { useNotices } from './features/notices/hooks/useNotices'
import {
  applyFilters,
  buildNotificationList,
  paginate,
  scoreNoticesByProfile,
  sortNotices,
} from './features/notices/utils/filtering'
import { generateDraftWithLM } from './api/lmStudioApi'
import BookmarkPage from './features/pages/BookmarkPage'
import DashboardPage from './features/pages/DashboardPage'
import DetailPage from './features/pages/DetailPage'
import DraftPage from './features/pages/DraftPage'
import DraftPageV2 from './features/pages/draft-v2/DraftPageV2'
import DraftListPage from './features/pages/DraftListPage'
import MyDraftsPage from './features/drafts/MyDraftsPage'
import MaterialsLibraryPage from './features/pages/MaterialsLibraryPage'
import ArchivePage from './features/drafts/ArchivePage'
import NotificationPage from './features/pages/NotificationPage'
import NotificationSettingsPage from './features/pages/NotificationSettingsPage'
import SearchPage from './features/pages/SearchPage'
import SettingsPage from './features/pages/SettingsPage'
import { useDrafts } from './features/notices/hooks/useDrafts'
import { useProfile } from './features/notices/hooks/useProfile'
// DEMO_NOTICES / DEMO_DRAFTS 폴백 완전 제거 (2026-05-25) — 실데이터만 표시
import { env } from './config/env'
import { analysisApi } from './api/backendApi'

// v0.2 session storage key (DraftPageV2.jsx와 동일)
const V2_SESSION_STORAGE_KEY = 'ajin_v2_session_id'

// v0.2 session → DashboardPage draft 형식으로 정규화
// backend GET /api/analysis/sessions 응답 item shape:
//   { session_id, user_id, status, current_step, notice_id, notice_title, created_at, updated_at }
function v02SessionToDraft(s) {
  const sid = s.session_id || ''
  return {
    notice: {
      id: sid,
      origin: 'v0.2 분석',
      title: s.notice_title || (s.notice_id ? String(s.notice_id) : `세션 ${sid.slice(0, 8)}`),
    },
    completedSteps: Array.from(
      { length: Math.max(0, (s.current_step || 1) - 1) },
      (_, i) => i + 1,
    ),
    currentStep: s.current_step || 1,
    updatedAt: s.updated_at || s.created_at,
    _isV02: true,
    _sessionId: sid,
  }
}

// 의미있는 세션만 — list 응답엔 notice_schema_json이 없으므로 notice_id/title 또는 status 기준
function isMeaningfulSession(s) {
  if (s.status && s.status !== 'created') return true
  if (s.notice_id) return true
  if (s.notice_title) return true
  return false
}

const PER_PAGE = 30

// ── Draft 라우트 분기 (PRD §17.2 #5 / §21.2 #18) ──
// dev 환경 (VITE_ENABLE_ANALYSIS_DEV_MODE=true) → /draft-v2 (V2)
// 운영 환경 → /draft (V1, 기존)
// /draft 라우트 자체는 V1 그대로 유지 (Q3=b 결정, 절대 교체 X)
const isDevMode = import.meta.env.VITE_ENABLE_ANALYSIS_DEV_MODE === 'true'
const DRAFT_DEFAULT_ROUTE = isDevMode ? '/draft-v2' : '/draft'

function createProfileText(profileData) {
  return `${profileData.field} 분야 기업. ${profileData.summary}. 전략: ${profileData.strategy}. ${DEFAULT_AJIN_PROFILE}`
}

function App() {
  const { notices, errors, loading } = useNotices()
  const { bookmarks, isBookmarked, toggleBookmark, clearBookmarks } = useBookmarks()
  const { draftList, getDraft, saveDraft, removeDraft } = useDrafts()
  const { profileData, setProfileData, saveProfile } = useProfile()

  // 공고 검색/대시보드 — DEMO 폴백 제거. notices가 비면 빈 배열 노출.
  const displayNotices = notices
  // v0.2 sessions (user_id='anonymous' + meaningful 필터, 최근 10개)
  const [v02Drafts, setV02Drafts] = useState([])
  useEffect(() => {
    let cancelled = false
    analysisApi.listSessions({ userId: 'anonymous', limit: 50 })
      .then(res => {
        if (cancelled) return
        const items = res?.items || res?.sessions || []
        const normalized = items
          .filter(isMeaningfulSession)
          .sort((a, b) => new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at))
          .slice(0, 10)
          .map(v02SessionToDraft)
        setV02Drafts(normalized)
      })
      .catch(err => console.warn('[V02_SESSIONS_FETCH_FAILED]', err))
    return () => { cancelled = true }
  }, [])

  // Dashboard/사이드바: v0.2 sessions만 사용. v1 legacy draftList도 제거 (사용자 명시 — 샘플 데이터 X)
  // 빈 배열이면 사이드바에 "작성 중인 공고가 없습니다" 표시 (이미 처리됨)
  const displayDrafts = v02Drafts

  // 사이드바 X 버튼 핸들러 — v0.2면 backend soft delete + state 정리, v1이면 기존 removeDraft
  const handleRemoveDraft = async (id) => {
    const target = displayDrafts.find((d) => d.notice?.id === id || d._sessionId === id)
    if (target?._isV02 && target._sessionId) {
      try {
        await analysisApi.deleteSession(target._sessionId)
      } catch (e) {
        console.warn('[DELETE_SESSION_FAILED]', e)
      }
      setV02Drafts((prev) => prev.filter((d) => d._sessionId !== target._sessionId))
      return
    }
    removeDraft(id)
  }

  const navigate = useNavigate()
  const location = useLocation()
  const view = location.pathname.replace('/', '') || 'dashboard'
  const setView = (v) => {
    // 'draft' = 신규 작성 — 항상 새 세션으로 시작 (자료 업로드부터)
    if (v === 'draft') {
      sessionStorage.removeItem(V2_SESSION_STORAGE_KEY)
      setSelectedNotice(null)
      navigate(DRAFT_DEFAULT_ROUTE)
      return
    }
    // 'resumeDraft' = 초안 이어 작성 — 가장 최근 in-progress 세션 복원
    if (v === 'resumeDraft') {
      const recent = (displayDrafts || []).find((d) => d._isV02 && d._sessionId)
      if (!recent) {
        alert('작성 중인 초안이 없습니다.')
        return
      }
      sessionStorage.setItem(V2_SESSION_STORAGE_KEY, recent._sessionId)
      setSelectedNotice(null)
      navigate(DRAFT_DEFAULT_ROUTE)
      return
    }
    // 'library' = 자료실 (E-1 라우트는 E 그룹에서 등록)
    if (v === 'library') {
      navigate('/library')
      return
    }
    navigate('/' + v)
  }

  const [tab, setTab] = useState('card')
  const [selectedNotice, setSelectedNotice] = useState(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [draftError, setDraftError] = useState('')

  const [filters, setFilters] = useState({
    matchMode: '적합도(유사도)',
    selectedKeywords: [],
    selectedRegions: [],
    selectedSizes: [],
    selectedOrigins: [],
    searchTitle: '',
    sortBy: '적합도순',
    threshold: 0.02,
    page: 1,
  })

  const [settings, setSettings] = useState({
    profileData,
    simThreshold: 0.02,
    notiKeywordsStr: '자동차, 스마트공장, DX, 에너지',
    currentProfileText: DEFAULT_AJIN_PROFILE,
    notiKeywords: ['자동차', '스마트공장', 'DX', '에너지'],
  })

  const [draftState, setDraftState] = useState({
    diagStep: 1,
    projectGoal: '',
    corpName: '아진산업(주)',
    uploads: [],
    generatedText: '',
  })

  const keywordOptions = useMemo(() => Object.values(KEYWORD_GROUPS).flat(), [])

  const scoredNotices = useMemo(
    () => scoreNoticesByProfile(displayNotices, settings.currentProfileText),
    [displayNotices, settings.currentProfileText],
  )

  const originOptions = useMemo(() => {
    const set = new Set(scoredNotices.map((n) => n.origin).filter(Boolean))
    return [...set].sort()
  }, [scoredNotices])

  const filteredSorted = useMemo(() => {
    const filtered = applyFilters(scoredNotices, filters)
    return sortNotices(filtered, filters.sortBy)
  }, [scoredNotices, filters])

  const paged = useMemo(
    () => paginate(filteredSorted, filters.page, PER_PAGE),
    [filteredSorted, filters.page],
  )

  const notificationNotices = useMemo(
    () => buildNotificationList(scoredNotices, settings.simThreshold, settings.notiKeywords),
    [scoredNotices, settings.simThreshold, settings.notiKeywords],
  )

  const handleFilterChange = (patch) => setFilters((prev) => ({ ...prev, ...patch }))

  const resetFilters = () => setFilters((prev) => ({
    ...prev,
    matchMode: '적합도(유사도)',
    selectedKeywords: [],
    selectedRegions: [],
    selectedSizes: [],
    selectedOrigins: [],
    searchTitle: '',
    sortBy: '적합도순',
    page: 1,
  }))

  const openDetail = (notice) => {
    if (!notice) return;

    // 💡 [무적 방어 코드] 빈 값이나 깨진 데이터가 들어와도 화면이 절대 뻗지 않도록 모든 값을 강제 변환
    let safeDate = new Date();
    try {
      if (notice.date) {
        const parsed = new Date(notice.date);
        if (!isNaN(parsed.getTime())) safeDate = parsed;
      }
    } catch (e) {
      console.warn('날짜 파싱 방어:', e);
    }

    const safeNotice = {
      ...notice,
      id: notice.id || String(Math.random()),
      title: notice.title ? String(notice.title) : '제목 없음',
      content: notice.content ? String(notice.content) : '내용이 없습니다.',
      target: notice.target ? String(notice.target) : '공고 본문 참조',
      benefit: notice.benefit ? String(notice.benefit) : '공고 본문 참조',
      documents: notice.documents ? String(notice.documents) : '공고 본문 참조',
      limit: notice.limit ? String(notice.limit) : '공고 본문 참조',
      category: notice.category ? String(notice.category) : '',
      region: notice.region ? String(notice.region) : '전국',
      period: notice.period ? String(notice.period) : '-',
      origin: notice.origin ? String(notice.origin) : '-',
      jrsdInsttNm: notice.jrsdInsttNm ? String(notice.jrsdInsttNm) : '-',
      excInsttNm: notice.excInsttNm ? String(notice.excInsttNm) : '-',
      reqstMthPapersCn: notice.reqstMthPapersCn ? String(notice.reqstMthPapersCn) : '공고 본문 참조',
      refrncNm: notice.refrncNm ? String(notice.refrncNm) : '공고 본문 참조',
      url: notice.url ? String(notice.url) : '',
      rceptEngnHmpgUrl: notice.rceptEngnHmpgUrl ? String(notice.rceptEngnHmpgUrl) : '',
      ajin_similarity: Number(notice.ajin_similarity) || 0,
      fileNm: notice.fileNm ? String(notice.fileNm) : '',
      printFileNm: notice.printFileNm ? String(notice.printFileNm) : '',
      date: safeDate,
    };
    
    setSelectedNotice(safeNotice)
    setView('detail')
  }

  const saveSettings = () => {
    setSettings((prev) => {
      const nextProfileText = createProfileText(prev.profileData)
      const nextKeywords = prev.notiKeywordsStr.split(',').map((k) => k.trim()).filter(Boolean)
      setFilters((f) => ({ ...f, threshold: prev.simThreshold }))
      saveProfile(prev.profileData)  // DB에 저장 (비동기, 실패해도 무시)
      return { ...prev, currentProfileText: nextProfileText, notiKeywords: nextKeywords }
    })
    setView('dashboard')
  }

  const onDraftChange = (key, value) => setDraftState((prev) => ({ ...prev, [key]: value }))

  const generateDraft = useCallback(async () => {
    if (!selectedNotice) return
    setIsGenerating(true)
    setDraftError('')
    try {
      const text = await generateDraftWithLM({ notice: selectedNotice, draft: draftState })
      setDraftState((prev) => ({ ...prev, generatedText: text }))
    } catch (err) {
      setDraftError(err.message ?? 'LM Studio 연결 실패')
    } finally {
      setIsGenerating(false)
    }
  }, [selectedNotice, draftState])

  const sidebarViews = ['dashboard', 'search', 'bookmark', 'notification', 'draft-list', 'myDrafts', 'archive']
  const showSidebar = sidebarViews.includes(view)

  return (
    <div className="min-h-screen bg-background">
      <TopNav
        view={view}
        onMove={setView}
        notificationCount={notificationNotices.length}
        bookmarkCount={bookmarks.length}
      />

      <div className="pt-14">
        <div className="max-w-[1600px] mx-auto flex">
          {showSidebar && (
            <Sidebar
              profileData={settings.profileData}
              onMove={setView}
              draftList={displayDrafts}
              onResumeDraft={(draft) => {
                if (draft?._isV02 && draft._sessionId) {
                  // v0.2 resume: sessionStorage 설정 후 navigate 직접 호출 — setView('draft')는 sessionStorage를 지워서 신규 세션으로 가버림
                  sessionStorage.setItem(V2_SESSION_STORAGE_KEY, draft._sessionId)
                  setSelectedNotice(null)
                  navigate(DRAFT_DEFAULT_ROUTE)
                  return
                }
                setSelectedNotice(draft.notice)
                navigate(DRAFT_DEFAULT_ROUTE)
              }}
              onRemoveDraft={handleRemoveDraft}
            />
          )}

          <main className={cn('flex-1 px-6 py-6', showSidebar ? 'max-w-[calc(1600px-16rem)]' : 'max-w-[1340px] mx-auto')}>
            <Routes>
              <Route path="/" element={
                <DashboardPage
                  totalNotices={scoredNotices.length}
                  matchedCount={notificationNotices.length}
                  bookmarkCount={bookmarks.length}
                  draftsInProgress={displayDrafts}
                  scoredNotices={scoredNotices}
                  onMove={setView}
                  onResumeDraft={(draft) => {
                    if (draft?._isV02 && draft._sessionId) {
                      sessionStorage.setItem(V2_SESSION_STORAGE_KEY, draft._sessionId)
                      setSelectedNotice(null)
                      setView('draft')
                      return
                    }
                    setSelectedNotice(draft.notice)
                    setView('draft')
                  }}
                  onOpenDetail={openDetail}
                />
              } />
              <Route path="/dashboard" element={
                <DashboardPage
                  totalNotices={scoredNotices.length}
                  matchedCount={notificationNotices.length}
                  bookmarkCount={bookmarks.length}
                  draftsInProgress={displayDrafts}
                  scoredNotices={scoredNotices}
                  onMove={setView}
                  onResumeDraft={(draft) => {
                    if (draft?._isV02 && draft._sessionId) {
                      sessionStorage.setItem(V2_SESSION_STORAGE_KEY, draft._sessionId)
                      setSelectedNotice(null)
                      setView('draft')
                      return
                    }
                    setSelectedNotice(draft.notice)
                    setView('draft')
                  }}
                  onOpenDetail={openDetail}
                />
              } />
              <Route path="/search" element={
                <SearchPage
                  loading={loading}
                  errors={errors}
                  allCount={scoredNotices.length}
                  filteredCount={filteredSorted.length}
                  filters={filters}
                  options={{ keywordOptions, regions: REGION_OPTIONS, sizes: SIZE_OPTIONS, origins: originOptions }}
                  pageState={paged}
                  onFilterChange={handleFilterChange}
                  onReset={resetFilters}
                  onMovePage={(page) => handleFilterChange({ page })}
                  onOpenDetail={openDetail}
                  tab={tab}
                  onTabChange={setTab}
                  isBookmarked={isBookmarked}
                  onToggleBookmark={toggleBookmark}
                />
              } />
              <Route path="/bookmark" element={
                <BookmarkPage
                  bookmarks={bookmarks}
                  notices={displayNotices}
                  onOpenDetail={openDetail}
                  onToggleBookmark={toggleBookmark}
                  onClearAll={clearBookmarks}
                />
              } />
              <Route path="/notification" element={
                <NotificationPage
                  notices={notificationNotices}
                  threshold={settings.simThreshold}
                  onBack={() => setView('dashboard')}
                  onOpenDetail={openDetail}
                />
              } />
              <Route path="/notiSettings" element={
                <NotificationSettingsPage
                  settings={settings}
                  onChange={(key, value) => setSettings((prev) => ({ ...prev, [key]: value }))}
                  onSave={saveSettings}
                  onBack={() => setView('dashboard')}
                />
              } />
              <Route path="/detail" element={
                <DetailPage
                  notice={selectedNotice}
                  onBack={() => setView('search')}
                  onStartDraft={() => {
                    setDraftState((prev) => ({ ...prev, diagStep: 1 }))
                    // selectedNotice 유지한 채 이동 — setView('draft')는 notice를 null로 초기화해버림
                    sessionStorage.removeItem(V2_SESSION_STORAGE_KEY)
                    navigate(DRAFT_DEFAULT_ROUTE)
                  }}
                  isBookmarked={selectedNotice ? isBookmarked(selectedNotice.id) : false}
                  onToggleBookmark={() => selectedNotice && toggleBookmark(selectedNotice)}
                />
              } />
              <Route path="/settings" element={
                <SettingsPage
                  settings={settings}
                  onChange={(key, value) => setSettings((prev) => ({ ...prev, [key]: value }))}
                  onSave={saveSettings}
                  onBack={() => setView('dashboard')}
                />
              } />
              <Route path="/draft" element={
                <DraftPage
                  notice={selectedNotice}
                  profileData={settings.profileData}
                  savedDraft={selectedNotice ? getDraft(selectedNotice.id) : null}
                  onSaveDraft={saveDraft}
                  onBack={() => setView('detail')}
                  onComplete={() => setView('myDrafts')}
                />
              } />
              {/* V2 라우트 — VITE_ENABLE_ANALYSIS_DEV_MODE=true 시만 노출 (PRD §17.2 #5 / §21.2 #18) */}
              {/* selectedNotice props로 자동업로드 (PRD §3.6 경로 A) */}
              {import.meta.env.VITE_ENABLE_ANALYSIS_DEV_MODE === 'true' && (
                <Route path="/draft-v2" element={<DraftPageV2 selectedNotice={selectedNotice} onRestoreNotice={setSelectedNotice} />} />
              )}
              <Route path="/draft-list" element={
                <DraftListPage
                  draftList={displayDrafts}
                  onResumeDraft={(draft) => {
                    if (draft?._isV02 && draft._sessionId) {
                      sessionStorage.setItem(V2_SESSION_STORAGE_KEY, draft._sessionId)
                      setSelectedNotice(null)
                      navigate(DRAFT_DEFAULT_ROUTE)
                      return
                    }
                    setSelectedNotice(draft.notice)
                    navigate(DRAFT_DEFAULT_ROUTE)
                  }}
                />
              } />
              <Route path="/myDrafts" element={
                <MyDraftsPage
                  onMove={setView}
                  onResumeDraft={(draft) => {
                    const snap = draft.notice_snapshot || {}
                    setSelectedNotice({
                      id: draft.notice_id,
                      title: snap.title || snap.full_title || '',
                      origin: snap.origin || '',
                      region: snap.region || '전국',
                      period: snap.period || '',
                      date: snap.date ? new Date(snap.date) : new Date(),
                      target: snap.target || '',
                      benefit: snap.benefit || '',
                      documents: snap.documents || '',
                      content: snap.content || '',
                      ajin_similarity: snap.ajin_similarity || 0,
                    })
                    // Q2=a: myDrafts 재개는 V1 강제 (state 호환 보호 — V2와 draft state 구조 다름)
                    navigate('/draft')
                  }}
                />
              } />
              <Route path="/library" element={<MaterialsLibraryPage />} />
              <Route path="/archive" element={
                <ArchivePage onMove={setView} />
              } />
            </Routes>
          </main>
        </div>
      </div>
    </div>
  )
}

export default App