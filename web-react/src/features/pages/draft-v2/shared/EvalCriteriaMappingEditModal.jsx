// AJIN BizAI v0.2.1 V3 — 평가기준 매핑 편집 모달 (5단 구조)
//
// 5단: head + info + body(left read-only / right edit) + diff strip + foot
//
// 닫기:
//   - [✕] / ESC / backdrop 클릭
//   - PATCH in-flight 중에는 모든 닫기 비활성
//   - V3 1차: 미저장 변경 확인 모달 없음 (단순 닫기)
//
// 저장 흐름:
//   1. validateEvalCriteriaDraft → blockers 있으면 차단 메시지 표시
//   2. buildEvalCriteriaPatchPayload (allowlist)
//   3. PATCH 호출 → 응답 item 전체 onSaved 콜백
//   4. 응답 받은 후 부모가 state 갱신 + 모달 닫기

import { useEffect, useMemo, useState } from 'react'
import { X, Loader2, AlertCircle, CheckCircle2, History } from 'lucide-react'
import {
  SCOPE_VALUES,
  MAPPING_TYPE_VALUES,
  validateEvalCriteriaDraft,
  buildEvalCriteriaPatchPayload,
} from '../../../../lib/evalCriteriaMappingAdapter'
import { analysisApi } from '../../../../api/backendApi'
import EvalCriteriaQuestionPicker from './EvalCriteriaQuestionPicker'
import EvalCriteriaHistoryModal from './EvalCriteriaHistoryModal'

const SCOPE_HINT = {
  question: '특정 문항 1개',
  section: '섹션 내 다수',
  document: '문서 전체',
}
const MAPPING_TYPE_HINT = {
  direct: '직접 매핑',
  indirect: '간접 반영',
  context: '맥락 반영',
}

export default function EvalCriteriaMappingEditModal({
  open,
  sessionId,
  criteriaId,        // 기존 (case 1) 또는 신규 생성된 ID (case 2)
  criteriaItem,      // { criteria_name, weight, scope, mapped_questions, mapping_type, confidence, mapped_by, history_count, reason, ... }
  formData,          // FormSchema (sections + questions)
  validQuestionIds,  // FormSchema에서 추출된 question_id 배열 (race 처리용)
  onClose,
  onSaved,           // (responseItem) => void — PATCH 응답 item 전체
}) {
  // ─── draft state ─────────────────────────────────────────────────
  const [scope, setScope] = useState(criteriaItem?.scope || 'section')
  const [mappingType, setMappingType] = useState(criteriaItem?.mapping_type || 'direct')
  const [mappedQuestions, setMappedQuestions] = useState(criteriaItem?.mapped_questions || [])
  const [reason, setReason] = useState(criteriaItem?.reason || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  // V3 2차: history sub-modal + 미저장 확인 inline panel
  const [showHistory, setShowHistory] = useState(false)
  const [showCloseConfirm, setShowCloseConfirm] = useState(false)

  // 초기값 snapshot (isDirty 판정용)
  const initialSnapshot = useMemo(() => ({
    scope: criteriaItem?.scope || 'section',
    mapping_type: criteriaItem?.mapping_type || 'direct',
    mapped_questions: [...(criteriaItem?.mapped_questions || [])].sort(),
    reason: criteriaItem?.reason || '',
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [criteriaItem, open])

  const isDirty = useMemo(() => {
    if (scope !== initialSnapshot.scope) return true
    if (mappingType !== initialSnapshot.mapping_type) return true
    if (reason !== initialSnapshot.reason) return true
    const cur = [...mappedQuestions].sort()
    const init = initialSnapshot.mapped_questions
    if (cur.length !== init.length) return true
    for (let i = 0; i < cur.length; i++) if (cur[i] !== init[i]) return true
    return false
  }, [scope, mappingType, mappedQuestions, reason, initialSnapshot])

  // criteriaItem 변경 시 draft 초기화
  useEffect(() => {
    if (open) {
      setScope(criteriaItem?.scope || 'section')
      setMappingType(criteriaItem?.mapping_type || 'direct')
      setMappedQuestions(criteriaItem?.mapped_questions || [])
      setReason(criteriaItem?.reason || '')
      setError(null)
      setShowHistory(false)
      setShowCloseConfirm(false)
    }
  }, [open, criteriaItem])

  // 안전한 닫기 (isDirty면 confirm)
  const requestClose = () => {
    if (busy) return
    if (showHistory) { setShowHistory(false); return }
    if (isDirty) { setShowCloseConfirm(true); return }
    onClose?.()
  }
  const confirmCloseDiscard = () => {
    setShowCloseConfirm(false)
    onClose?.()
  }
  const cancelClose = () => setShowCloseConfirm(false)

  // ESC 키 닫기
  useEffect(() => {
    if (!open) return
    const handleEsc = (e) => {
      if (e.key !== 'Escape') return
      if (busy) return
      if (showHistory) { setShowHistory(false); return }
      if (showCloseConfirm) { setShowCloseConfirm(false); return }
      requestClose()
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, busy, showHistory, showCloseConfirm, isDirty])

  // ─── validation ──────────────────────────────────────────────────
  const draft = useMemo(() => ({
    scope,
    mapping_type: mappingType,
    mapped_questions: mappedQuestions,
    reason,
    confidence: criteriaItem?.confidence,
    criteria_name: criteriaItem?.criteria_name,
    weight: criteriaItem?.weight,
  }), [scope, mappingType, mappedQuestions, reason, criteriaItem])

  const validation = useMemo(
    () => validateEvalCriteriaDraft({ draft, validQuestionIds }),
    [draft, validQuestionIds]
  )

  // ─── diff 계산 ───────────────────────────────────────────────────
  const diff = useMemo(() => {
    if (!criteriaItem) return []
    const out = []
    const compare = (field, before, after) => {
      const eq = Array.isArray(before) && Array.isArray(after)
        ? before.length === after.length && before.every((v, i) => v === after[i])
        : before === after
      out.push({ field, before, after, changed: !eq })
    }
    compare('scope', criteriaItem.scope, scope)
    compare('mapping_type', criteriaItem.mapping_type, mappingType)
    compare('mapped_questions', criteriaItem.mapped_questions || [], mappedQuestions)
    compare('mapped_by', criteriaItem.mapped_by, 'user')
    return out
  }, [criteriaItem, scope, mappingType, mappedQuestions])

  // ─── 저장 ────────────────────────────────────────────────────────
  const handleSave = async () => {
    if (validation.blockers.length > 0) return
    setBusy(true)
    setError(null)
    try {
      const payload = buildEvalCriteriaPatchPayload({
        sessionId,
        draft: {
          ...draft,
          criteria_name: criteriaItem?.criteria_name,
          weight: criteriaItem?.weight,
        },
        validQuestionIds,
      })
      const res = await analysisApi.updateEvalCriteriaMapping({
        criteriaId,
        payload,
      })
      onSaved?.(res)
    } catch (err) {
      console.warn('[EVAL_CRITERIA_PATCH_FAILED]', err)
      setError(err.message || '저장 실패')
    } finally {
      setBusy(false)
    }
  }

  // backdrop 클릭 (isDirty면 confirm)
  const handleBackdrop = (e) => {
    if (e.target === e.currentTarget) requestClose()
  }

  if (!open) return null

  const canSave = validation.blockers.length === 0
  const formatVal = (v) => Array.isArray(v) ? `[${v.join(', ')}]` : String(v ?? '')

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/45 backdrop-blur-sm p-4"
      onClick={handleBackdrop}
    >
      <div className="relative bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden">

        {/* ── 1. head ── */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-base font-semibold text-slate-900">평가기준 매핑 편집</h2>
            <span className="text-xs font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
              {criteriaItem?.criteria_name} · {criteriaItem?.weight ?? 0}점
            </span>
          </div>
          <button
            onClick={requestClose}
            disabled={busy}
            className="text-slate-400 hover:text-slate-600 disabled:opacity-40 p-1"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* ── 2. info ── */}
        <div className="px-6 py-2.5 bg-indigo-50 border-b border-indigo-100 text-xs text-indigo-900 leading-relaxed">
          AI가 자동 생성한 평가기준 → 문항 매핑을 검토하고 수정합니다.
          저장된 매핑은 사용자 편집값으로 보존됩니다.
          Step 4 패널 즉시 반영은 다음 버전(V4)에서 제공됩니다.
        </div>

        {/* ── 3. body ── */}
        <div className="flex-1 overflow-y-auto grid grid-cols-[260px_1fr]">

          {/* left: read-only */}
          <div className="border-r border-slate-200 p-4 bg-slate-50/50 text-xs space-y-3">
            <h3 className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">현재 매핑</h3>
            <div>
              <div className="text-[10px] text-slate-500 mb-0.5">scope</div>
              <span className="font-mono text-xs text-slate-700 bg-white border border-slate-200 rounded px-2 py-0.5">
                {criteriaItem?.scope}
              </span>
            </div>
            <div>
              <div className="text-[10px] text-slate-500 mb-0.5">mapping_type</div>
              <span className="font-mono text-xs text-slate-700 bg-white border border-slate-200 rounded px-2 py-0.5">
                {criteriaItem?.mapping_type}
              </span>
            </div>
            <div>
              <div className="text-[10px] text-slate-500 mb-0.5">
                confidence <span className="text-slate-400">(read-only · V3 1차)</span>
              </div>
              <span className="font-mono text-xs text-slate-500 bg-white border border-slate-200 rounded px-2 py-0.5">
                {criteriaItem?.confidence ?? '-'}
              </span>
            </div>
            <hr className="border-dashed border-slate-200" />
            <div>
              <div className="text-[10px] text-slate-500 mb-1">매핑 문항 ({(criteriaItem?.mapped_questions || []).length})</div>
              <div className="flex flex-wrap gap-1">
                {(criteriaItem?.mapped_questions || []).map(qid => (
                  <span key={qid} className="font-mono text-[10px] bg-indigo-50 text-indigo-900 border border-indigo-100 rounded px-1.5 py-0.5">
                    {qid}
                  </span>
                ))}
                {(criteriaItem?.mapped_questions || []).length === 0 && (
                  <span className="text-[10px] text-slate-400">(없음)</span>
                )}
              </div>
            </div>
            <hr className="border-dashed border-slate-200" />
            <div className="flex items-center gap-2 text-[10px] text-slate-500 flex-wrap">
              <span className={`px-1.5 py-0.5 rounded border ${
                criteriaItem?.mapped_by === 'user'
                  ? 'bg-blue-100 text-blue-800 border-blue-200'
                  : 'bg-slate-100 text-slate-600 border-slate-200'
              }`}>
                {criteriaItem?.mapped_by === 'user' ? '✎ 사용자 편집됨' : 'AI 자동'}
              </span>
              {(criteriaItem?.history_count ?? 0) > 0 ? (
                <button
                  type="button"
                  onClick={() => setShowHistory(true)}
                  disabled={busy}
                  className="inline-flex items-center gap-1 text-amber-700 bg-amber-50 border border-amber-200 hover:bg-amber-100 px-1.5 py-0.5 rounded transition-colors disabled:opacity-50"
                  title="변경 이력 보기"
                >
                  <History className="w-2.5 h-2.5" />
                  이력 {criteriaItem.history_count}건 보기
                </button>
              ) : (
                <span>· 이력 0건</span>
              )}
            </div>
            <div className="text-[9px] text-slate-400 font-mono break-all">
              criteria_id: {criteriaId}
            </div>
          </div>

          {/* right: edit */}
          <div className="p-5 space-y-5 text-sm">
            {/* scope */}
            <div>
              <h3 className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 mb-2">scope</h3>
              <div className="flex gap-2">
                {SCOPE_VALUES.map(s => (
                  <label
                    key={s}
                    className={`flex-1 border-2 rounded-md px-3 py-2 cursor-pointer text-xs flex items-center gap-2 transition-colors ${
                      scope === s
                        ? 'bg-indigo-50 border-indigo-600 text-indigo-900 font-semibold'
                        : 'border-slate-200 bg-white hover:border-slate-300'
                    }`}
                  >
                    <input
                      type="radio"
                      name="scope"
                      value={s}
                      checked={scope === s}
                      onChange={() => setScope(s)}
                      disabled={busy}
                      className="accent-indigo-600"
                    />
                    <div className="flex-1">
                      <div>{s}</div>
                      <div className="text-[9px] text-slate-500 font-normal">{SCOPE_HINT[s]}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* mapping_type */}
            <div>
              <h3 className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 mb-2">mapping_type</h3>
              <div className="flex gap-2">
                {MAPPING_TYPE_VALUES.map(t => (
                  <label
                    key={t}
                    className={`flex-1 border-2 rounded-md px-3 py-2 cursor-pointer text-xs flex items-center gap-2 transition-colors ${
                      mappingType === t
                        ? 'bg-emerald-50 border-emerald-600 text-emerald-900 font-semibold'
                        : 'border-slate-200 bg-white hover:border-slate-300'
                    }`}
                  >
                    <input
                      type="radio"
                      name="mtype"
                      value={t}
                      checked={mappingType === t}
                      onChange={() => setMappingType(t)}
                      disabled={busy}
                      className="accent-emerald-600"
                    />
                    <div className="flex-1">
                      <div>{t}</div>
                      <div className="text-[9px] text-slate-500 font-normal">{MAPPING_TYPE_HINT[t]}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* mapped_questions */}
            <div>
              <h3 className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 mb-2">
                매핑 문항 선택 <span className="text-slate-400 normal-case">(FormSchema 기준)</span>
              </h3>
              <EvalCriteriaQuestionPicker
                formData={formData}
                selectedQuestionIds={mappedQuestions}
                onChange={setMappedQuestions}
                disabled={busy}
              />
              {/* 선택된 chip */}
              <div className="mt-2 flex flex-wrap gap-1.5 min-h-[26px] p-2 bg-slate-50 border border-dashed border-slate-200 rounded">
                {mappedQuestions.length === 0 && scope === 'question' && (
                  <span className="text-[11px] text-amber-700">
                    question scope에서는 최소 1개 문항을 선택해야 합니다.
                  </span>
                )}
                {mappedQuestions.length === 0 && scope !== 'question' && (
                  <span className="text-[11px] text-slate-400">선택된 문항 없음</span>
                )}
                {mappedQuestions.map(qid => (
                  <span
                    key={qid}
                    className="inline-flex items-center gap-1 bg-indigo-600 text-white text-[11px] font-mono rounded-full pl-2 pr-1 py-0.5"
                  >
                    {qid}
                    <button
                      type="button"
                      onClick={() => setMappedQuestions(mappedQuestions.filter(x => x !== qid))}
                      disabled={busy}
                      className="w-4 h-4 rounded-full bg-white/25 hover:bg-white/40 flex items-center justify-center"
                    >
                      <X className="w-2.5 h-2.5" />
                    </button>
                  </span>
                ))}
              </div>
            </div>

            {/* reason */}
            <div>
              <h3 className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 mb-2">
                수정 사유 <span className="text-rose-600 normal-case">(필수)</span>
              </h3>
              <textarea
                value={reason}
                onChange={e => setReason(e.target.value)}
                disabled={busy}
                rows={3}
                placeholder="예: 기술성 평가는 추진 계획(III)의 기술 개발 항목과 일정표를 함께 봐야 함. 기술정보(I-1)만으로는 부족."
                className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-indigo-600 focus:ring-1 focus:ring-indigo-600 resize-y disabled:opacity-60"
              />
              {!reason.trim() && (
                <p className="text-[11px] text-rose-600 mt-1">* 수정 사유는 필수입니다</p>
              )}
            </div>

            {/* validation blockers / warnings */}
            {validation.blockers.length > 0 && (
              <div className="bg-rose-50 border border-rose-200 rounded p-2.5 text-xs text-rose-800 space-y-0.5">
                <div className="flex items-center gap-1 font-semibold">
                  <AlertCircle className="w-3.5 h-3.5" /> 저장 차단 사유
                </div>
                {validation.blockers.map((b, i) => (
                  <div key={i} className="ml-4">· {b.message}</div>
                ))}
              </div>
            )}
            {validation.warnings.length > 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded p-2.5 text-xs text-amber-800 space-y-0.5">
                <div className="flex items-center gap-1 font-semibold">⚠️ 경고 (저장 가능)</div>
                {validation.warnings.map((w, i) => (
                  <div key={i} className="ml-4">· {w.message}</div>
                ))}
              </div>
            )}
            {error && (
              <div className="bg-rose-50 border border-rose-200 rounded p-2.5 text-xs text-rose-800">
                저장 실패: {error}
              </div>
            )}
          </div>
        </div>

        {/* ── 4. diff strip ── */}
        <div className="bg-slate-900 text-slate-300 px-6 py-3 font-mono text-[11px] border-t border-slate-200">
          <div className="text-[9px] uppercase tracking-wider text-slate-400 mb-1.5 font-sans font-semibold">
            변경 사항 (Before → After)
          </div>
          {diff.map(({ field, before, after, changed }) => (
            <div key={field} className="flex gap-3 py-0.5 items-baseline">
              <span className="text-slate-500 min-w-[130px]">{field}</span>
              {changed ? (
                <>
                  <span className="text-rose-400 line-through decoration-rose-400/50">{formatVal(before)}</span>
                  <span className="text-slate-600">→</span>
                  <span className="text-emerald-400 font-semibold">{formatVal(after)}</span>
                </>
              ) : (
                <span className="text-slate-500">{formatVal(before)} (변경 없음)</span>
              )}
            </div>
          ))}
        </div>

        {/* ── 5. foot ── */}
        <div className="px-6 py-3.5 border-t border-slate-200 bg-slate-50 flex items-center justify-between gap-3">
          <div className="text-[10px] text-slate-500 font-mono">
            저장 시 PATCH /api/analysis/eval-criteria-mappings/{`{id}`} 호출
          </div>
          <div className="flex gap-2">
            <button
              onClick={requestClose}
              disabled={busy}
              className="px-3.5 py-1.5 text-xs border border-slate-200 bg-white rounded hover:bg-slate-50 disabled:opacity-50"
            >
              취소
            </button>
            <button
              onClick={handleSave}
              disabled={busy || !canSave}
              className="px-4 py-1.5 text-xs bg-indigo-600 text-white rounded font-semibold hover:bg-indigo-700 disabled:opacity-50 inline-flex items-center gap-1.5"
            >
              {busy ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> 저장 중...
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5" /> 변경사항 저장
                </>
              )}
            </button>
          </div>
        </div>

        {/* V3 2차: 미저장 변경 확인 inline panel (main modal 위 overlay) */}
        {showCloseConfirm && (
          <div
            className="absolute inset-0 z-10 flex items-center justify-center bg-slate-900/30 backdrop-blur-[1px] rounded-lg"
            onClick={e => { if (e.target === e.currentTarget) cancelClose() }}
          >
            <div className="bg-white rounded-md shadow-xl max-w-sm w-full mx-4 p-5 border border-slate-200">
              <div className="flex items-start gap-3 mb-3">
                <AlertCircle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-sm font-semibold text-slate-900 mb-1">변경사항이 저장되지 않았습니다</h4>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    저장하지 않고 닫으면 편집 내용이 사라집니다. 계속 닫을까요?
                  </p>
                </div>
              </div>
              <div className="flex justify-end gap-2 mt-4">
                <button
                  onClick={cancelClose}
                  className="px-3 py-1.5 text-xs border border-slate-200 bg-white rounded hover:bg-slate-50"
                >
                  계속 편집
                </button>
                <button
                  onClick={confirmCloseDiscard}
                  className="px-3 py-1.5 text-xs bg-rose-600 text-white rounded hover:bg-rose-700"
                >
                  변경 무시하고 닫기
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* V3 2차: 변경 이력 sub-modal (z-60) */}
      <EvalCriteriaHistoryModal
        open={showHistory}
        history={criteriaItem?.history || []}
        criteriaName={criteriaItem?.criteria_name}
        onClose={() => setShowHistory(false)}
      />
    </div>
  )
}
