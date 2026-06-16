/**
 * 내 사업계획서 페이지 (4탭: 작성중 | 작성완료 | 제출완료 | 채택 진행)
 * 디자인 기준: design/내사업계획서_목업 (4).html
 */
import { useMemo, useState } from 'react'
import { useMyDrafts } from './hooks/useMyDrafts'
import StatusBadge from './components/StatusBadge'
import VersionHistory from './components/VersionHistory'
import ResultInputModal from './components/ResultInputModal'
import VersionReplaceModal from './components/VersionReplaceModal'
import DownloadButtons from './components/DownloadButtons'

const TABS = ['작성중', '작성완료', '제출완료', '채택']

function dday(noticeSnapshot) {
  const dateStr = noticeSnapshot?.date || noticeSnapshot?.period || ''
  if (!dateStr) return null
  const m = String(dateStr).match(/(\d{4}-\d{2}-\d{2})/)
  if (!m) return null
  const diff = Math.ceil((new Date(m[1]) - new Date()) / 86400000)
  return diff
}

function DdayBadge({ d }) {
  if (d === null) return null
  if (d > 0) return <span className="badge bg-rose-100 text-rose-800">D-{d}</span>
  if (d === 0) return <span className="badge bg-rose-100 text-rose-800">D-day</span>
  return (
    <>
      <span className="badge bg-amber-100 text-amber-800">D+{Math.abs(d)}</span>
      <span className="inline-flex items-center gap-1 text-xs text-amber-700 font-medium">
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        정리 권장
      </span>
    </>
  )
}

export default function MyDraftsPage({ onResumeDraft, onMove }) {
  const { drafts, loading, error, updateStatus, updateResult, archiveDraft, createVersion, refetch } = useMyDrafts({ archived: false })
  const [activeTab, setActiveTab] = useState('작성중')
  const [search, setSearch] = useState('')
  const [resultModal, setResultModal] = useState(null)   // { draftId, noticeId }
  const [replaceModal, setReplaceModal] = useState(null) // { noticeId, versions }

  const counts = useMemo(() => {
    const map = { '작성중': 0, '작성완료': 0, '제출완료': 0, '채택': 0 }
    drafts.forEach(d => {
      const s = d.status
      if (s === '작성중' || s === '미제출') map['작성중'] += 1
      else if (s === '작성완료') map['작성완료'] += 1
      else if (s === '제출완료') map['제출완료'] += 1
      else if (s === '채택') map['채택'] += 1
    })
    return map
  }, [drafts])

  const filtered = useMemo(() => {
    let items = drafts.filter(d => {
      if (activeTab === '작성중') return d.status === '작성중' || d.status === '미제출'
      return d.status === activeTab
    })
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      items = items.filter(d =>
        (d.notice_snapshot?.title || '').toLowerCase().includes(q) ||
        (d.notice_snapshot?.origin || '').toLowerCase().includes(q)
      )
    }
    // 정렬: D-day 촉박순, 마감 지난 건 뒤
    items = [...items].sort((a, b) => {
      const da = dday(a.notice_snapshot)
      const db2 = dday(b.notice_snapshot)
      if (da === null && db2 === null) return 0
      if (da === null) return 1
      if (db2 === null) return -1
      // 마감 지남(음수) → 뒤로
      const aExpired = da < 0, bExpired = db2 < 0
      if (aExpired !== bExpired) return aExpired ? 1 : -1
      return da - db2
    })
    return items
  }, [drafts, activeTab, search])

  const handleCreateVersion = async (noticeId, versions) => {
    if (versions.length >= 3) {
      setReplaceModal({ noticeId, versions })
      return
    }
    await createVersion(noticeId)
  }

  const handleSubmitComplete = async (draftId) => {
    await updateStatus(draftId, '제출완료')
  }

  if (loading) return <div className="flex items-center justify-center h-64 text-slate-500">불러오는 중...</div>
  if (error) return <div className="flex items-center justify-center h-64 text-rose-600">오류: {error}</div>

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-7xl mx-auto px-6 py-8">

        {/* 헤더 */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900 mb-1">내 사업계획서</h1>
          <p className="text-sm text-slate-500">
            작성 중 <span className="font-semibold text-slate-700">{counts['작성중']}건</span>
            <span className="mx-2 text-slate-300">·</span>
            작성 완료 <span className="font-semibold text-slate-700">{counts['작성완료']}건</span>
            <span className="mx-2 text-slate-300">·</span>
            제출 완료 <span className="font-semibold text-slate-700">{counts['제출완료']}건</span>
            <span className="mx-2 text-slate-300">·</span>
            채택 진행 <span className="font-semibold text-slate-700">{counts['채택']}건</span>
          </p>
        </div>

        {/* 검색 + 탭 */}
        <div className="bg-white border border-slate-200 rounded-lg p-4 mb-6">
          <div className="relative mb-3">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="공고명, 기관, 키워드로 검색..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 text-sm border border-slate-200 rounded-md focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div className="flex items-center gap-2">
            {TABS.map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 rounded-md text-sm font-medium border ${
                  activeTab === tab
                    ? 'bg-slate-900 text-white border-slate-900'
                    : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                }`}
              >
                {tab === '채택' ? '채택 진행' : tab}{' '}
                <span className={activeTab === tab ? 'opacity-80' : 'text-slate-400'}>{counts[tab]}</span>
              </button>
            ))}
            <button
              onClick={() => onMove?.('archive')}
              className="ml-auto px-4 py-2 rounded-md text-sm font-medium border bg-white text-slate-600 border-slate-200 hover:bg-slate-50 flex items-center gap-1.5"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
              </svg>
              보관함
            </button>
          </div>
        </div>

        {/* 카드 목록 */}
        {filtered.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-lg p-12 text-center text-slate-500">
            {activeTab} 항목이 없습니다.
          </div>
        ) : (
          <section className="mb-6">
            <h2 className="text-base font-semibold text-slate-900 mb-3">
              {activeTab === '채택' ? '채택 진행' : activeTab} ({filtered.length}건)
            </h2>
            <div className="space-y-3">
              {filtered.map(draft => (
                <DraftCard
                  key={draft.id}
                  draft={draft}
                  tab={activeTab}
                  onResumeDraft={onResumeDraft}
                  onArchive={(id) => archiveDraft(id)}
                  onSubmitComplete={handleSubmitComplete}
                  onCreateVersion={handleCreateVersion}
                  onOpenResultModal={(draftId) => setResultModal({ draftId, noticeId: draft.notice_id })}
                />
              ))}
            </div>
          </section>
        )}
      </div>

      {resultModal && (
        <ResultInputModal
          draftId={resultModal.draftId}
          onConfirm={async (result, date, memo) => {
            await updateResult(resultModal.draftId, result, date, memo)
            setResultModal(null)
          }}
          onClose={() => setResultModal(null)}
        />
      )}

      {replaceModal && (
        <VersionReplaceModal
          versions={replaceModal.versions}
          onConfirm={async (replaceVersion) => {
            await createVersion(replaceModal.noticeId, undefined, replaceVersion)
            setReplaceModal(null)
          }}
          onClose={() => setReplaceModal(null)}
        />
      )}
    </div>
  )
}

function DraftCard({ draft, tab, onResumeDraft, onArchive, onSubmitComplete, onCreateVersion, onOpenResultModal }) {
  const [versionOpen, setVersionOpen] = useState(false)
  const snap = draft.notice_snapshot || {}
  const d = dday(snap)
  const older = draft.all_versions?.filter(v => v.version < draft.version) || []

  return (
    <div className={`bg-white border rounded-lg overflow-hidden transition-all duration-150 hover:-translate-y-px hover:shadow-md ${
      d !== null && d < 0 ? 'border-amber-200' : 'border-slate-200'
    } ${tab === '작성완료' ? 'border-2 border-emerald-200' : ''}`}>
      <div className={`p-5 ${tab !== '작성중' ? 'p-4' : ''}`}>

        {tab === '작성완료' && (
          <div className="flex items-center gap-2 mb-3 text-xs text-emerald-700 font-medium">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span>작성 완료</span>
          </div>
        )}

        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <StatusBadge status={draft.status} />
              {draft.version > 1 && (
                <span className="badge bg-blue-100 text-blue-700">v{draft.version}</span>
              )}
              {tab === '작성완료' && snap.aiScore && (
                <span className="badge bg-slate-100 text-slate-700">AI 평가 {snap.aiScore}점</span>
              )}
              <DdayBadge d={d} />
            </div>
            <h3 className="text-base font-semibold text-slate-900 mb-1">
              {snap.title || snap.full_title || '(제목 없음)'}
            </h3>
            <p className="text-sm text-slate-500">
              {snap.origin || ''}{snap.region ? ` · ${snap.region}` : ''}
              {snap.period ? ` · 마감 ${snap.period}` : ''}
            </p>
          </div>

          <div className="flex gap-2 shrink-0 flex-wrap justify-end">
            {tab === '작성중' && (
              <>
                <button className="px-4 py-1.5 text-sm border border-slate-300 rounded-md hover:bg-slate-50">상세</button>
                <button onClick={() => onArchive(draft.id)} className="px-4 py-1.5 text-sm border border-slate-300 rounded-md hover:bg-slate-50 text-slate-600">보관함 이동</button>
                <button onClick={() => onResumeDraft?.(draft)} className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium">이어 작성</button>
              </>
            )}
            {tab === '작성완료' && (
              <></>
            )}
            {tab === '제출완료' && (
              <>
                <button className="px-3 py-1.5 text-xs border border-slate-300 rounded-md hover:bg-slate-50">상세</button>
                <DownloadButtons size="xs" />
                <button onClick={() => onOpenResultModal(draft.id)} className="px-3 py-1.5 text-xs border border-emerald-300 text-emerald-700 rounded-md hover:bg-emerald-50">채택</button>
                <button onClick={() => onOpenResultModal(draft.id)} className="px-3 py-1.5 text-xs border border-slate-300 text-slate-600 rounded-md hover:bg-slate-50">미채택</button>
                <button onClick={() => onCreateVersion(draft.notice_id, draft.all_versions)} className="px-3 py-1.5 text-xs border border-slate-300 rounded-md hover:bg-slate-50">새 버전 만들기</button>
              </>
            )}
            {tab === '채택' && (
              <>
                <button className="px-3 py-1.5 text-xs border border-slate-300 rounded-md hover:bg-slate-50">상세</button>
                <DownloadButtons size="xs" />
                <button onClick={() => alert('개발 중인 기능입니다')} className="relative px-3 py-1.5 text-xs border border-slate-300 rounded-md text-slate-500">
                  후속 보고서 작성
                  <span className="absolute -top-2 -right-2 inline-flex items-center px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 text-[9px] font-medium">개발중</span>
                </button>
              </>
            )}
          </div>
        </div>

        {/* 작성완료 버튼 행 */}
        {tab === '작성완료' && (
          <div className="flex items-center gap-2 pt-3 border-t border-slate-100 flex-wrap mt-3">
            <DownloadButtons />
            <button onClick={() => onArchive(draft.id)} className="px-4 py-1.5 text-sm border border-slate-300 rounded-md hover:bg-slate-50 text-slate-600">보관함 이동</button>
            <button onClick={() => onCreateVersion(draft.notice_id, draft.all_versions)} className="px-4 py-1.5 text-sm border border-slate-300 rounded-md hover:bg-slate-50">새 버전 만들기</button>
            <button onClick={() => onSubmitComplete(draft.id)} className="ml-auto px-4 py-1.5 text-sm bg-slate-900 text-white rounded-md hover:bg-slate-800 font-medium">제출 완료 처리</button>
          </div>
        )}

        {/* 작성중 진행률 */}
        {tab === '작성중' && (
          <div className="mt-3">
            <div className="flex items-center gap-4 mb-2 text-sm">
              <span className="text-slate-700 font-medium">STEP {draft.current_step}/5</span>
              <span className="text-slate-500">{stepLabel(draft.current_step)}</span>
              <span className="text-slate-400 text-xs ml-auto">
                {draft.updated_at ? `마지막 저장 ${timeAgo(draft.updated_at)}` : ''}
              </span>
            </div>
            <div className="h-1 bg-slate-200 rounded-full overflow-hidden">
              <div className="h-full bg-blue-600 rounded-full transition-all" style={{ width: `${(draft.current_step / 5) * 100}%` }} />
            </div>
          </div>
        )}

        {/* 채택 진행 상세 */}
        {tab === '채택' && draft.result_memo && (
          <p className="text-xs text-slate-500 mt-1">메모: {draft.result_memo}</p>
        )}

        {/* 버전 펼침 토글 */}
        {older.length > 0 && (
          <button
            onClick={() => setVersionOpen(!versionOpen)}
            className="flex items-center gap-1 mt-3 pt-3 border-t border-slate-100 text-xs text-slate-500 hover:text-slate-700 w-full"
          >
            <svg className={`w-3 h-3 transition-transform ${versionOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
            이전 버전 {older.length}개
          </button>
        )}
      </div>

      {versionOpen && older.length > 0 && (
        <VersionHistory versions={older} />
      )}
    </div>
  )
}

function stepLabel(step) {
  const labels = { 1: '공고 확인', 2: '자료 검사 단계', 3: '초안 작성 단계', 4: '평가 단계', 5: '최종 확인' }
  return labels[step] || ''
}

function timeAgo(isoStr) {
  if (!isoStr) return ''
  const diff = (Date.now() - new Date(isoStr)) / 1000
  if (diff < 60) return '방금 전'
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`
  return `${Math.floor(diff / 86400)}일 전`
}
