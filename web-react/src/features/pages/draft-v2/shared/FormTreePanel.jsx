// AJIN BizAI v0.2 — Tab 2 좌측: 추출 항목 트리
// 출처: mockup_final.html 848~1052 / PRD §13.2 FormSchema
// form_prd/4.md + 5.md: 항목 수정/추가/제외 UI v0.1 추가
//   - 항목별 ✏️ 버튼 (호버 시 표시)
//   - section별 [+] 버튼
//   - "제외 항목 보임/숨김" 토글
//   - excludedSet 기반 회색·취소선

import { useMemo, useState } from 'react'

const FORM_MOCK = {
  stats: { total: 18, sections: 5, tables: 2 },
  sections: [
    {
      id: 'I', title: '신청기업 개요', count: '3 문항',
      questions: [
        { id: 'I-1', title: '기업 현황', status: 'ok', meta: ['800자', '필수', '가이드 2', 'p.2'] },
        { id: 'I-2', title: '주요 제품/서비스', status: 'ok', meta: ['1,000자', '필수', '첨부 1', 'p.3'] },
        { id: 'I-3', title: '보유 역량 (인증·특허·실적)', status: 'ok', meta: ['1,200자', '첨부 3', 'p.3'] },
      ],
    },
    {
      id: 'II', title: '사업 추진 필요성', count: '2 문항',
      questions: [
        { id: 'II-1', title: '시장 문제', status: 'weak', meta: ['1,500자', '필수', '가이드 3', 'p.5 · 현재 위치'] },
        { id: 'II-2', title: '지원 필요성', status: 'missing', meta: ['1,000자', '필수', 'p.5'] },
      ],
    },
    {
      id: 'III', title: '세부 추진 계획', count: '1 표 + 2 문항',
      questions: [
        { id: 'III-T1', title: '추진 일정표', status: 'ok', meta: ['표 (4열)', '필수', 'p.5'] },
        { id: 'III-1', title: '기술 개발 계획', status: 'ok', meta: ['2,000자', '필수', '가이드 4', 'p.6'] },
        { id: 'III-2', title: '사업화 전략', status: 'weak', meta: ['1,500자', '필수', 'p.7'] },
      ],
    },
    {
      id: 'IV', title: '예산 계획', count: '2 문항',
      questions: [
        { id: 'IV-1', title: '총괄 예산', status: 'ok', meta: ['표 (5열)', '필수', 'p.8'] },
        { id: 'IV-2', title: '예산 산출 근거', status: 'weak', meta: ['1,500자', '첨부 2', 'p.9'] },
      ],
    },
    {
      id: 'V', title: '기대 효과', count: '3 문항',
      questions: [
        { id: 'V-1', title: '정량적 기대효과', status: 'ok', meta: ['1,000자', '필수', 'p.11'] },
        { id: 'V-2', title: '정성적 기대효과', status: 'ok', meta: ['800자', 'p.11'] },
        { id: 'V-3', title: '파급 효과', status: 'ok', meta: ['600자', 'p.12'] },
      ],
    },
  ],
}

const STATUS_BADGE = {
  ok: { label: '작성 가능', cls: 'bg-emerald-50 text-emerald-700' },
  weak: { label: '근거 부족', cls: 'bg-amber-50 text-amber-700' },
  missing: { label: '자료 없음', cls: 'bg-red-50 text-red-700' },
  // 2026-05-18: 사용자 "작성 제외" 표시 — mapping/draft에서 skip
  excluded: { label: '작성 제외', cls: 'bg-slate-200 text-slate-600' },
}

export default function FormTreePanel({
  selectedQid,
  onSelect,
  formData = FORM_MOCK,
  // form_prd/4.md + 5.md: 수정/추가/제외 핸들러 (없으면 버튼 미표시)
  onEditQuestion = null,   // (questionId) => void
  onAddInSection = null,   // (sectionId) => void — 섹션 끝에 추가
  onToggleExclude = null,  // (questionId, nextExcluded:boolean) => void
  // 2026-05-18: 신규 핸들러 (Tree CRUD)
  onAddSection = null,        // () => void — 트리 상단 "+ 섹션 추가"
  onRenameSection = null,     // (sectionId) => void
  onDeleteSection = null,     // (sectionId) => void
  onReorderSection = null,    // (sectionId, direction: 'up'|'down') => void
  onAddAboveQuestion = null,  // (sectionId, questionId) => void
  onAddBelowQuestion = null,  // (sectionId, questionId) => void
  onDeleteQuestion = null,    // (questionId) => void — hard delete
  onMoveQuestion = null,      // (questionId, currentSectionId) => void
}) {
  // 2026-05-18: excluded 항목 default 표시 (회색 + 작성 제외 badge로 시각 구분)
  //   사용자가 제외했어도 트리에 그대로 보임 → 다시 ↺로 해제 가능
  //   카운트는 deriveStatusStats에서 제외됨 (display는 유지)
  const [showExcluded, setShowExcluded] = useState(true)
  // 2026-05-18: section collapse/expand 상태 (default: 모두 펼침 — 기존 UX 보존)
  const [collapsedSections, setCollapsedSections] = useState(() => new Set())
  const toggleCollapse = (sid) => {
    setCollapsedSections(prev => {
      const next = new Set(prev)
      if (next.has(sid)) next.delete(sid); else next.add(sid)
      return next
    })
  }
  const collapseAll = () => {
    setCollapsedSections(new Set((formData?.sections || []).map(s => s.id)))
  }
  const expandAll = () => {
    setCollapsedSections(new Set())
  }

  // excludedSet: formApiResp.excluded_question_ids ?? []
  const excludedSet = useMemo(
    () => new Set(Array.isArray(formData?.excluded_question_ids) ? formData.excluded_question_ids : []),
    [formData?.excluded_question_ids]
  )

  const canEdit = !!onEditQuestion
  const canAdd = !!onAddInSection
  const canToggleExclude = !!onToggleExclude
  const canAddSection = !!onAddSection
  const canSectionCrud = !!(onRenameSection || onDeleteSection || onReorderSection)
  const sectionCount = (formData?.sections || []).length

  return (
    <div className="bg-white border border-slate-200 rounded-md flex flex-col h-full overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-200">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-slate-900">추출 항목 트리</span>
          <div className="flex gap-3 text-xs text-slate-500">
            <span>전체 <strong className="text-slate-900">{formData.stats.total}</strong></span>
            <span>섹션 <strong className="text-slate-900">{formData.stats.sections}</strong></span>
            <span>표 <strong className="text-slate-900">{formData.stats.tables}</strong></span>
          </div>
        </div>
        {/* 제외 항목 토글 + 안내 */}
        {canToggleExclude && (
          <div className="mt-2 flex items-center justify-between">
            <label className="flex items-center gap-1.5 text-[11px] text-slate-600 cursor-pointer">
              <input
                type="checkbox"
                checked={showExcluded}
                onChange={(e) => setShowExcluded(e.target.checked)}
              />
              제외 항목 보기 ({excludedSet.size})
            </label>
            <span className="text-[10px] text-amber-700" title="v0.1: 매핑/초안 단계 제외 반영은 후속 작업">
              ⓘ v0.1 트리만
            </span>
          </div>
        )}
        {/* 2026-05-18: 트리 액션 — 섹션 추가 / 모두 접기·펴기 */}
        {(canAddSection || sectionCount > 1) && (
          <div className="mt-2 flex items-center justify-between gap-2">
            {canAddSection ? (
              <button
                type="button"
                onClick={onAddSection}
                className="text-[11px] px-2 py-1 border border-indigo-300 bg-indigo-50 text-indigo-900 rounded hover:bg-indigo-100"
                title="새 섹션 추가"
              >
                + 섹션 추가
              </button>
            ) : <span />}
            <div className="flex gap-1">
              <button
                type="button"
                onClick={collapseAll}
                className="text-[10px] px-1.5 py-0.5 text-slate-500 hover:text-slate-900"
                title="모두 접기"
              >▼ 접기</button>
              <button
                type="button"
                onClick={expandAll}
                className="text-[10px] px-1.5 py-0.5 text-slate-500 hover:text-slate-900"
                title="모두 펼치기"
              >▶ 펴기</button>
            </div>
          </div>
        )}
      </div>

      <div className="overflow-y-auto flex-1">
        {formData.sections.map((sec, secIdx) => {
          const visibleQuestions = (sec.questions || []).filter(q => {
            if (excludedSet.has(q.id || q.question_id)) return showExcluded
            return true
          })
          const isCollapsed = collapsedSections.has(sec.id)
          const isFirst = secIdx === 0
          const isLast = secIdx === formData.sections.length - 1
          return (
            <div key={sec.id} className="border-b border-slate-100 last:border-0">
              <div className="group/sec px-4 py-2 bg-slate-50 flex items-center justify-between sticky top-0">
                <button
                  type="button"
                  onClick={() => toggleCollapse(sec.id)}
                  className="flex items-center gap-1.5 text-sm font-medium text-slate-700 hover:text-slate-900 flex-1 text-left"
                  title={isCollapsed ? '펼치기' : '접기'}
                >
                  <span className="text-slate-400 text-xs w-3">{isCollapsed ? '▶' : '▼'}</span>
                  <span className="font-mono text-slate-400 mr-1">{sec.id}.</span>
                  <span className="flex-1">{sec.title}</span>
                </button>
                <div className="flex items-center gap-1">
                  <span className="font-mono text-[10px] text-slate-400">{sec.count}</span>
                  {/* 2026-05-18: section CRUD hover 버튼 */}
                  {canSectionCrud && (
                    <span className="flex items-center gap-0.5 opacity-0 group-hover/sec:opacity-100 transition">
                      {onReorderSection && !isFirst && (
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); onReorderSection(sec.id, 'up') }}
                          className="text-[10px] px-1 py-0.5 rounded hover:bg-white text-slate-600 hover:text-slate-900"
                          title="위로 이동"
                        >↑</button>
                      )}
                      {onReorderSection && !isLast && (
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); onReorderSection(sec.id, 'down') }}
                          className="text-[10px] px-1 py-0.5 rounded hover:bg-white text-slate-600 hover:text-slate-900"
                          title="아래로 이동"
                        >↓</button>
                      )}
                      {onRenameSection && (
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); onRenameSection(sec.id) }}
                          className="text-[10px] px-1 py-0.5 rounded hover:bg-white text-slate-600 hover:text-slate-900"
                          title="섹션 이름 수정"
                        >✏️</button>
                      )}
                      {onDeleteSection && (
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); onDeleteSection(sec.id) }}
                          className="text-[10px] px-1 py-0.5 rounded hover:bg-rose-50 text-rose-600 hover:text-rose-800"
                          title="섹션 삭제"
                        >🗑</button>
                      )}
                    </span>
                  )}
                  {canAdd && (
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); onAddInSection(sec.id) }}
                      className="text-xs px-1.5 py-0.5 rounded border border-slate-300 hover:bg-white text-slate-600 hover:text-slate-900"
                      title="이 섹션에 문항 추가 (끝)"
                    >
                      +
                    </button>
                  )}
                </div>
              </div>
              {/* collapsed면 questions 영역 렌더 안 함 */}
              {!isCollapsed && visibleQuestions.map((q) => {
                const qid = q.id || q.question_id
                const isSelected = qid === selectedQid
                const isExcluded = excludedSet.has(qid)
                return (
                  <div
                    key={qid}
                    className={`group w-full border-l-2 transition ${
                      isSelected
                        ? 'border-indigo-950 bg-indigo-50/50'
                        : 'border-transparent hover:bg-slate-50'
                    } ${isExcluded ? 'opacity-50' : ''}`}
                  >
                    <div
                      role="button"
                      tabIndex={0}
                      onClick={() => onSelect?.(qid)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect?.(qid) } }}
                      className="w-full text-left px-4 py-2.5 cursor-pointer"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-xs text-slate-500 min-w-[42px]">{qid}</span>
                        <span className={`text-sm flex-1 ${isExcluded ? 'text-slate-500' : 'text-slate-900'}`}>
                          {q.title}
                        </span>
                        {q.status && STATUS_BADGE[q.status] && (
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${STATUS_BADGE[q.status].cls}`}>
                            {STATUS_BADGE[q.status].label}
                          </span>
                        )}
                        {/* 액션 버튼: ✏️ ⬆➕ ⬇➕ ↔ 🗑 🚫 — 호버 시 표시 */}
                        <span className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition">
                          {canEdit && !isExcluded && (
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); onEditQuestion(qid) }}
                              className="text-[11px] px-1.5 py-0.5 rounded border border-slate-300 bg-white hover:bg-slate-100 text-slate-700"
                              title="문항 수정"
                            >
                              ✏️
                            </button>
                          )}
                          {onAddAboveQuestion && !isExcluded && (
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); onAddAboveQuestion(sec.id, qid) }}
                              className="text-[11px] px-1.5 py-0.5 rounded border border-slate-300 bg-white hover:bg-slate-100 text-slate-700"
                              title="위에 문항 추가"
                            >⬆+</button>
                          )}
                          {onAddBelowQuestion && !isExcluded && (
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); onAddBelowQuestion(sec.id, qid) }}
                              className="text-[11px] px-1.5 py-0.5 rounded border border-slate-300 bg-white hover:bg-slate-100 text-slate-700"
                              title="아래에 문항 추가"
                            >⬇+</button>
                          )}
                          {onMoveQuestion && !isExcluded && (
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); onMoveQuestion(qid, sec.id) }}
                              className="text-[11px] px-1.5 py-0.5 rounded border border-slate-300 bg-white hover:bg-slate-100 text-slate-700"
                              title="다른 섹션으로 이동"
                            >↔</button>
                          )}
                          {canToggleExclude && (
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); onToggleExclude(qid, !isExcluded) }}
                              className="text-[11px] px-1.5 py-0.5 rounded border border-slate-300 bg-white hover:bg-slate-100 text-slate-700"
                              title={isExcluded ? '제외 해제 (트리 복원)' : '제외 (회색 표시)'}
                            >
                              {isExcluded ? '↺' : '🚫'}
                            </button>
                          )}
                          {onDeleteQuestion && (
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); onDeleteQuestion(qid) }}
                              className="text-[11px] px-1.5 py-0.5 rounded border border-rose-300 bg-white hover:bg-rose-50 text-rose-600 hover:text-rose-800"
                              title="문항 영구 삭제 (DB)"
                            >🗑</button>
                          )}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1 ml-[50px]">
                        {q.meta?.map((m, i) => (
                          <span key={i} className="text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded">
                            {m}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export { FORM_MOCK }
