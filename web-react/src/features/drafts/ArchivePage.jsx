/**
 * 보관함 페이지 (미채택 + 미제출)
 * 디자인 기준: design/보관함_목업.html
 */
import { useState, useMemo } from 'react'
import { useMyDrafts } from './hooks/useMyDrafts'
import StatusBadge from './components/StatusBadge'
import VersionHistory from './components/VersionHistory'
import DownloadButtons from './components/DownloadButtons'

const FILTER_OPTIONS = ['전체', '미채택', '미제출']

export default function ArchivePage({ onMove }) {
  const { drafts, loading, error, permanentDelete, permanentDeleteBulk, restoreDraft, refetch } =
    useMyDrafts({ archived: true })
  const [activeFilter, setActiveFilter] = useState('전체')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState(new Set())
  const [sort, setSort] = useState('최신순')

  const counts = useMemo(() => {
    const c = { '전체': drafts.length, '미채택': 0, '미제출': 0 }
    drafts.forEach(d => { if (d.status === '미채택') c['미채택']++; else c['미제출']++ })
    return c
  }, [drafts])

  const filtered = useMemo(() => {
    let items = activeFilter === '전체' ? drafts : drafts.filter(d => d.status === activeFilter)
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      items = items.filter(d =>
        (d.notice_snapshot?.title || '').toLowerCase().includes(q) ||
        (d.notice_snapshot?.origin || '').toLowerCase().includes(q) ||
        (d.result_memo || '').toLowerCase().includes(q)
      )
    }
    if (sort === '최신순') items = [...items].sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
    else if (sort === '오래된 순') items = [...items].sort((a, b) => new Date(a.updated_at) - new Date(b.updated_at))
    return items
  }, [drafts, activeFilter, search, sort])

  const rejected = filtered.filter(d => d.status === '미채택')
  const unsubmitted = filtered.filter(d => d.status !== '미채택')

  const toggleSelect = (id) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const handleBulkDelete = async () => {
    if (!window.confirm(`선택한 ${selected.size}개를 영구 삭제하시겠습니까? 복구할 수 없습니다.`)) return
    await permanentDeleteBulk([...selected])
    setSelected(new Set())
  }

  const handleDelete = async (id) => {
    if (!window.confirm('영구 삭제하시겠습니까? 복구할 수 없습니다.')) return
    await permanentDelete(id)
    setSelected(prev => { const n = new Set(prev); n.delete(id); return n })
  }

  if (loading) return <div className="flex items-center justify-center h-64 text-slate-500">불러오는 중...</div>
  if (error) return <div className="flex items-center justify-center h-64 text-rose-600">오류: {error}</div>

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-7xl mx-auto px-6 py-8">

        {/* 헤더 */}
        <div className="mb-6">
          <button
            onClick={() => onMove?.('myDrafts')}
            className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-3"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            내 사업계획서로 돌아가기
          </button>
          <div className="flex items-center gap-2 mb-1">
            <svg className="w-6 h-6 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
            </svg>
            <h1 className="text-2xl font-bold text-slate-900">보관함</h1>
            <span className="text-base text-slate-500 font-normal ml-1">({drafts.length}건)</span>
          </div>
          <p className="text-sm text-slate-500">종료된 사업계획서 보관소 · 다운로드해서 새 작성에 참고할 수 있습니다</p>
        </div>

        {/* 안내 */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-6 flex items-start gap-2">
          <svg className="w-4 h-4 text-blue-600 mt-0.5 shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
          <p className="text-xs text-blue-900 leading-relaxed">
            파일을 다운받아 새 사업계획서 작성 시 <strong>참고자료로 업로드</strong>하면 시스템이 자료를 분석하여 활용합니다.
          </p>
        </div>

        {/* 검색 + 필터 */}
        <div className="bg-white border border-slate-200 rounded-lg p-4 mb-6">
          <div className="relative mb-3">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="공고명, 기관, 키워드, 메모로 검색..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 text-sm border border-slate-200 rounded-md focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-slate-500 font-medium mr-1">필터:</span>
            {FILTER_OPTIONS.map(f => (
              <button
                key={f}
                onClick={() => setActiveFilter(f)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium border ${
                  activeFilter === f
                    ? 'bg-slate-900 text-white border-slate-900'
                    : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                }`}
              >
                {f} <span className={activeFilter === f ? 'opacity-80' : 'text-slate-400'}>{counts[f]}</span>
              </button>
            ))}
            <div className="ml-auto">
              <select
                value={sort}
                onChange={e => setSort(e.target.value)}
                className="text-xs border border-slate-200 rounded-md px-2 py-1.5 bg-white"
              >
                <option>최신순</option>
                <option>오래된 순</option>
              </select>
            </div>
          </div>
        </div>

        {/* 미채택 */}
        {(activeFilter === '전체' || activeFilter === '미채택') && rejected.length > 0 && (
          <section className="mb-8">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-1 h-5 bg-rose-400 rounded-full" />
              <h2 className="text-base font-semibold text-slate-900">미채택 ({rejected.length}건)</h2>
            </div>
            <div className="space-y-2">
              {rejected.map(draft => (
                <ArchiveCard key={draft.id} draft={draft} selected={selected.has(draft.id)} onToggle={toggleSelect} onDelete={handleDelete} />
              ))}
            </div>
          </section>
        )}

        {/* 미제출 */}
        {(activeFilter === '전체' || activeFilter === '미제출') && unsubmitted.length > 0 && (
          <section className="mb-8">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-1 h-5 bg-amber-400 rounded-full" />
              <h2 className="text-base font-semibold text-slate-900">미제출 ({unsubmitted.length}건)</h2>
            </div>
            <div className="space-y-2">
              {unsubmitted.map(draft => (
                <ArchiveCard key={draft.id} draft={draft} selected={selected.has(draft.id)} onToggle={toggleSelect} onDelete={handleDelete} />
              ))}
            </div>
          </section>
        )}

        {filtered.length === 0 && (
          <div className="bg-white border border-slate-200 rounded-lg p-12 text-center text-slate-500">보관함이 비어있습니다.</div>
        )}
      </div>

      {/* 일괄 삭제 바 */}
      {selected.size > 0 && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t-2 border-slate-200 px-6 py-3 z-40">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <span className="text-sm text-slate-700"><span className="font-semibold">{selected.size}개</span> 선택됨</span>
            <div className="flex gap-2">
              <button onClick={() => setSelected(new Set())} className="px-4 py-1.5 text-sm border border-slate-300 rounded-md hover:bg-slate-50">선택 해제</button>
              <button onClick={handleBulkDelete} className="px-4 py-1.5 text-sm border border-rose-300 text-rose-700 rounded-md hover:bg-rose-50">선택 항목 영구 삭제</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ArchiveCard({ draft, selected, onToggle, onDelete }) {
  const [versionOpen, setVersionOpen] = useState(false)
  const snap = draft.notice_snapshot || {}
  const older = draft.all_versions?.filter(v => v.version < draft.version) || []
  const isCompleted = draft.status === '미제출' && snap.aiScore

  return (
    <div className={`bg-white border rounded-lg overflow-hidden transition-all duration-150 hover:-translate-y-px hover:shadow-md ${
      isCompleted ? 'border-2 border-emerald-200' : 'border-slate-200'
    }`}>
      <div className="p-4">
        <div className="flex items-start gap-4">
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onToggle(draft.id)}
            className="mt-1.5 w-4 h-4 rounded border-slate-300 cursor-pointer"
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <StatusBadge status={draft.status} />
              {isCompleted && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-100 text-emerald-800">작성완료</span>
              )}
              {snap.aiScore && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">AI 평가 {snap.aiScore}점</span>
              )}
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">v{draft.version}</span>
              {draft.result_date && (
                <span className="text-xs text-slate-500">{String(draft.result_date).slice(0, 10)}</span>
              )}
            </div>
            <h3 className="text-sm font-semibold text-slate-900">{snap.title || snap.full_title || '(제목 없음)'}</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              {snap.origin || ''}{snap.region ? ` · ${snap.region}` : ''}
              {snap.period ? ` · 마감 ${snap.period} (지남)` : ''}
            </p>
            {draft.result_memo && (
              <p className="text-xs text-slate-600 italic mt-1">📝 {draft.result_memo}</p>
            )}
            {/* 미제출 작성중: STEP + 진행률 */}
            {draft.status === '미제출' && !snap.aiScore && (
              <div className="mt-2">
                <div className="flex items-center gap-3 text-xs mb-1">
                  <span className="text-slate-700 font-medium">STEP {draft.current_step}/5</span>
                  <span className="text-slate-500">{stepLabel(draft.current_step)}</span>
                </div>
                <div style={{ height: 4, background: '#e2e8f0', borderRadius: 2 }}>
                  <div style={{ height: '100%', width: `${(draft.current_step / 5) * 100}%`, background: '#2563eb', borderRadius: 2 }} />
                </div>
              </div>
            )}
          </div>
          <div className="flex gap-2 shrink-0">
            <DownloadButtons size="xs" />
            <button
              onClick={() => onDelete(draft.id)}
              className="px-3 py-1.5 text-xs border border-rose-300 text-rose-700 rounded-md hover:bg-rose-50"
            >
              영구 삭제
            </button>
          </div>
        </div>

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
      {versionOpen && older.length > 0 && <VersionHistory versions={older} />}
    </div>
  )
}

function stepLabel(step) {
  const labels = { 1: '공고 확인', 2: '자료 검사 단계', 3: '초안 작성 단계', 4: '평가 단계', 5: '최종 확인' }
  return labels[step] || ''
}
