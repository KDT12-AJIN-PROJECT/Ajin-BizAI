// AJIN BizAI v0.2.1 V3 — FormSchema 기반 문항 선택 picker
//
// FormSchema race 처리 (사용자 추가 조건):
//   - sections 빈/로딩 중 → disabled + 안내 문구
//   - sections 정상 → section별 그룹 + checkbox

import { useMemo, useState } from 'react'
import { Search, X } from 'lucide-react'

export default function EvalCriteriaQuestionPicker({
  formData,                  // { sections: [{ id, title, questions: [{id, title, char_limit?}] }] }
  selectedQuestionIds = [],
  onChange,                  // (newSelectedIds: string[]) => void
  disabled = false,
}) {
  // V3 2차: 검색
  const [search, setSearch] = useState('')
  // FormSchema race: sections 빈 또는 로딩 중
  const hasFormSchema = !!(formData?.sections?.length)
  const effectiveDisabled = disabled || !hasFormSchema

  const allQuestions = useMemo(() => {
    if (!hasFormSchema) return []
    const out = []
    for (const sec of formData.sections) {
      const qs = (sec.questions || []).map(q => ({
        question_id: q.id,
        title: q.title || q.name || q.id,
        section_id: sec.id,
        section_title: sec.title || sec.name || sec.id,
        char_limit: q.char_limit,
      }))
      out.push(...qs)
    }
    return out
  }, [formData, hasFormSchema])

  const selectedSet = useMemo(() => new Set(selectedQuestionIds), [selectedQuestionIds])

  const toggle = (qid) => {
    if (effectiveDisabled) return
    const next = selectedSet.has(qid)
      ? selectedQuestionIds.filter(x => x !== qid)
      : [...selectedQuestionIds, qid]
    onChange?.(next)
  }

  if (!hasFormSchema) {
    return (
      <div className="border border-slate-200 rounded-md p-4 bg-amber-50/50 text-center">
        <p className="text-xs text-amber-700">
          ⏳ 양식 분석 진행 중입니다.
        </p>
        <p className="text-[11px] text-amber-700/80 mt-1">
          제출양식 분석이 완료되면 문항 선택이 가능합니다.
        </p>
      </div>
    )
  }

  // section별 그룹화 + 검색 필터
  const searchLower = search.trim().toLowerCase()
  const sectionGroups = formData.sections.map(sec => {
    const allQs = (sec.questions || []).map(q => ({
      id: q.id,
      title: q.title || q.name || q.id,
      char_limit: q.char_limit,
    }))
    const filtered = searchLower
      ? allQs.filter(q =>
          String(q.id).toLowerCase().includes(searchLower) ||
          String(q.title).toLowerCase().includes(searchLower)
        )
      : allQs
    return {
      id: sec.id,
      title: sec.title || sec.name || sec.id,
      allQuestions: allQs,
      questions: filtered,
      hidden: searchLower && filtered.length === 0,
    }
  })
  const visibleSections = sectionGroups.filter(s => !s.hidden)

  return (
    <div className="border border-slate-200 rounded-md overflow-hidden bg-white">
      {/* 검색 input */}
      <div className="px-2.5 py-2 border-b border-slate-200 bg-slate-50/60 flex items-center gap-2">
        <Search className="w-3.5 h-3.5 text-slate-400 shrink-0" />
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') e.preventDefault() }}
          disabled={effectiveDisabled}
          placeholder="문항 ID 또는 제목 검색..."
          className="flex-1 text-xs bg-transparent outline-none placeholder:text-slate-400 disabled:opacity-50"
        />
        {search && (
          <button
            type="button"
            onClick={() => setSearch('')}
            className="text-slate-400 hover:text-slate-600"
            title="검색 지우기"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {searchLower && visibleSections.length === 0 && (
        <div className="text-center text-xs text-slate-400 py-6">
          "{search}"에 일치하는 문항이 없습니다.
        </div>
      )}

      {visibleSections.map(sec => {
        const selectedInSection = sec.allQuestions.filter(q => selectedSet.has(q.id)).length
        return (
          <div key={sec.id}>
            <div className="bg-slate-50 px-3 py-1.5 border-b border-slate-200 flex items-center justify-between">
              <span className="text-[11px] font-semibold text-slate-600">{sec.title}</span>
              <span className="text-[10px] text-slate-400 font-mono">
                {selectedInSection} / {sec.allQuestions.length} 선택
              </span>
            </div>
            {sec.questions.length === 0 ? (
              <div className="px-3 py-2 text-[11px] text-slate-400">(문항 없음)</div>
            ) : sec.questions.map(q => {
              const isSelected = selectedSet.has(q.id)
              return (
                <label
                  key={q.id}
                  className={`flex items-center gap-2 px-3 py-1.5 text-xs border-b border-slate-100 cursor-pointer transition-colors
                    ${isSelected ? 'bg-indigo-50' : 'hover:bg-slate-50'}
                    ${effectiveDisabled ? 'opacity-60 cursor-not-allowed' : ''}`}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggle(q.id)}
                    disabled={effectiveDisabled}
                    className="accent-indigo-600"
                  />
                  <span className="font-mono text-[10px] text-slate-500 min-w-[44px]">{q.id}</span>
                  <span className="flex-1 text-slate-700 truncate">{q.title}</span>
                  {q.char_limit && (
                    <span className="text-[9px] text-slate-400 bg-slate-100 px-1 rounded">{q.char_limit}자</span>
                  )}
                </label>
              )
            })}
          </div>
        )
      })}
    </div>
  )
}
