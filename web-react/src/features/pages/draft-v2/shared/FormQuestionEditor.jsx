// AJIN BizAI v0.2 — form_prd/4.md + 5.md
// FormQuestion 편집/추가 통합 모달.
//
// Props:
//   open: boolean
//   mode: 'edit' | 'add'
//   question: edit 모드일 때 기존 question 객체 (backend 원본, question_id 포함)
//   sectionId: add 모드일 때 대상 section_id
//   sectionTitle: add 모드일 때 표시용 section.title
//   busy: 저장 중 disable
//   onClose: () => void
//   onSubmit: (payload) => void
//     edit: payload = { ...fields }
//     add:  payload = { ...fields, title } — backend에서 question_id 생성

import { useEffect, useState } from 'react'

const FIELD_LABEL_CLS = 'text-[11px] font-semibold uppercase tracking-wider text-slate-600'

function buildInitialState(question) {
  return {
    title: question?.title ?? '',
    source_page: question?.source_page != null ? String(question.source_page) : '',
    is_required: !!question?.is_required,
    is_table_item: !!question?.is_table_item,
    requirement: question?.requirement ?? '',
    // writing_guidelines: 배열 → 빈 줄 1개 구분된 텍스트로 표시
    writing_guidelines: Array.isArray(question?.writing_guidelines)
      ? question.writing_guidelines.join('\n\n')
      : '',
    max_length: question?.constraints?.max_length ?? 0,
    min_length: question?.constraints?.min_length ?? 0,
  }
}

export default function FormQuestionEditor({
  open,
  mode = 'edit',
  question = null,
  sectionId = null,
  sectionTitle = '',
  busy = false,
  onClose,
  onSubmit,
}) {
  const [state, setState] = useState(() => buildInitialState(question))
  const [error, setError] = useState(null)

  // open 또는 question 변경 시 state 초기화
  useEffect(() => {
    if (open) {
      setState(buildInitialState(question))
      setError(null)
    }
  }, [open, question])

  if (!open) return null

  const set = (k, v) => setState(prev => ({ ...prev, [k]: v }))

  const handleSubmit = (e) => {
    e?.preventDefault?.()
    setError(null)

    const title = state.title?.trim() || ''
    if (mode === 'add' && !title) {
      setError('제목(title)은 필수입니다.')
      return
    }

    // source_page: 빈 문자열이면 null, 아니면 정수 변환 시도
    let source_page = null
    if (state.source_page !== '' && state.source_page != null) {
      const n = Number(state.source_page)
      if (!Number.isInteger(n) || n < 1) {
        setError('source_page는 1 이상 정수여야 합니다.')
        return
      }
      source_page = n
    }

    // writing_guidelines: 빈 줄 기준 split
    const wg = String(state.writing_guidelines || '')
      .split(/\n\s*\n/)
      .map(s => s.trim())
      .filter(Boolean)

    // constraints: max/min_length
    const maxLen = Number(state.max_length)
    const minLen = Number(state.min_length)
    const constraints = {
      max_length: Number.isFinite(maxLen) && maxLen >= 0 ? maxLen : 0,
      min_length: Number.isFinite(minLen) && minLen >= 0 ? minLen : 0,
      format: question?.constraints?.format ?? null,
      page_limit: question?.constraints?.page_limit ?? null,
    }

    const payload = {
      title,
      source_page,
      is_required: !!state.is_required,
      is_table_item: !!state.is_table_item,
      requirement: state.requirement ?? '',
      writing_guidelines: wg,
      constraints,
    }
    onSubmit?.(payload)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          {/* 헤더 */}
          <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
            <div>
              <div className="text-base font-semibold text-slate-900">
                {mode === 'add' ? '문항 추가' : '문항 수정'}
              </div>
              <div className="text-[11px] text-slate-500 mt-0.5">
                {mode === 'add'
                  ? `섹션: ${sectionTitle || sectionId || '?'}`
                  : `ID: ${question?.question_id || '?'}`}
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className="text-slate-400 hover:text-slate-600 text-xl leading-none disabled:opacity-30"
            >
              ×
            </button>
          </div>

          {/* 본문 */}
          <div className="px-5 py-4 space-y-4">
            {/* title */}
            <div>
              <label className={FIELD_LABEL_CLS}>
                제목 {mode === 'add' && <span className="text-rose-600">*</span>}
              </label>
              <input
                type="text"
                value={state.title}
                onChange={(e) => set('title', e.target.value)}
                disabled={busy}
                placeholder="예: 기업 현황"
                className="mt-1 w-full px-3 py-2 border border-slate-200 rounded text-sm focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* source_page + plain checkboxes */}
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className={FIELD_LABEL_CLS}>source_page</label>
                <input
                  type="number"
                  min="1"
                  value={state.source_page}
                  onChange={(e) => set('source_page', e.target.value)}
                  disabled={busy}
                  placeholder="예: 3"
                  className="mt-1 w-full px-3 py-2 border border-slate-200 rounded text-sm"
                />
              </div>
              <div className="flex items-center gap-2 mt-5">
                <input
                  type="checkbox"
                  id="fqe-required"
                  checked={state.is_required}
                  onChange={(e) => set('is_required', e.target.checked)}
                  disabled={busy}
                />
                <label htmlFor="fqe-required" className="text-sm text-slate-700">필수 문항</label>
              </div>
              <div className="flex items-center gap-2 mt-5">
                <input
                  type="checkbox"
                  id="fqe-table"
                  checked={state.is_table_item}
                  onChange={(e) => set('is_table_item', e.target.checked)}
                  disabled={busy}
                />
                <label htmlFor="fqe-table" className="text-sm text-slate-700">표 항목</label>
              </div>
            </div>

            {/* constraints */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={FIELD_LABEL_CLS}>최대 글자수 (max_length)</label>
                <input
                  type="number"
                  min="0"
                  value={state.max_length}
                  onChange={(e) => set('max_length', e.target.value)}
                  disabled={busy}
                  className="mt-1 w-full px-3 py-2 border border-slate-200 rounded text-sm"
                />
              </div>
              <div>
                <label className={FIELD_LABEL_CLS}>최소 글자수 (min_length)</label>
                <input
                  type="number"
                  min="0"
                  value={state.min_length}
                  onChange={(e) => set('min_length', e.target.value)}
                  disabled={busy}
                  className="mt-1 w-full px-3 py-2 border border-slate-200 rounded text-sm"
                />
              </div>
            </div>

            {/* requirement */}
            <div>
              <label className={FIELD_LABEL_CLS}>작성 요구사항 (requirement)</label>
              <textarea
                rows={2}
                value={state.requirement}
                onChange={(e) => set('requirement', e.target.value)}
                disabled={busy}
                placeholder="작성 안내 텍스트"
                className="mt-1 w-full px-3 py-2 border border-slate-200 rounded text-sm resize-y"
              />
            </div>

            {/* writing_guidelines */}
            <div>
              <label className={FIELD_LABEL_CLS}>작성 가이드라인 (writing_guidelines)</label>
              <div className="text-[10px] text-slate-400 mt-0.5 mb-1">
                여러 항목은 <span className="font-mono">빈 줄</span>로 구분
              </div>
              <textarea
                rows={5}
                value={state.writing_guidelines}
                onChange={(e) => set('writing_guidelines', e.target.value)}
                disabled={busy}
                placeholder={'예시 1: 1,000자 이내로 작성\n\n예시 2: 정량적 수치 포함'}
                className="mt-1 w-full px-3 py-2 border border-slate-200 rounded text-sm resize-y font-mono"
              />
            </div>

            {error && (
              <div className="text-[12px] text-rose-700 bg-rose-50 border border-rose-200 rounded px-3 py-2">
                {error}
              </div>
            )}
          </div>

          {/* footer */}
          <div className="px-5 py-3 border-t border-slate-200 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className="text-sm px-3 py-1.5 border border-slate-200 rounded hover:bg-slate-50 disabled:opacity-40"
            >
              취소
            </button>
            <button
              type="submit"
              disabled={busy}
              className="text-sm px-4 py-1.5 bg-indigo-950 text-white rounded hover:bg-indigo-900 disabled:opacity-40"
            >
              {busy ? '저장 중...' : (mode === 'add' ? '추가' : '저장')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
