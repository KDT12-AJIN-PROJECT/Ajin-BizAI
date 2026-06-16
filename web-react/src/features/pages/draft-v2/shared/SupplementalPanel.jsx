// AJIN BizAI v0.2 — Tab 2 우측: 부족자료 보완 패널 (Phase 4-G-7a)
// 출처: mockup_final.html 1079~1253 + PRD §13.6 + PRD-13 §18.10
// API: /api/analysis/missing/{text,upload,bulk-upload,confirm} + /api/analysis/reanalyze

import { useState } from 'react'
import { analysisApi } from '../../../../api/backendApi'
import { logApi, handleFallback } from '../../../../lib/runtimeLog'
import {
  adaptMissingItems,
  adaptAutoMatchedCards,
  adaptPendingMatchCards,
  deriveSufficiency,
  adaptSelectedQuestion,
} from '../../../../lib/missingAdapter'

const ITEM_BTN_STYLE = {
  '직접입력': 'bg-slate-50 hover:bg-slate-100 text-slate-700',
  '파일업로드': 'bg-indigo-50 hover:bg-indigo-100 text-indigo-900',
  '원문보기': 'bg-slate-50 hover:bg-slate-100 text-slate-700',
  '나중에': 'bg-slate-50 hover:bg-slate-100 text-slate-500',
}

const ITEM_BTN_ICON = {
  '직접입력': '✎',
  '파일업로드': '📎',
  '원문보기': '👁',
  '나중에': '⏱',
}

export default function SupplementalPanel({
  devMode = false,
  sessionId,
  selectedQid,
  formData,
  formApiResp = null,   // 2026-05-19 Option C: raw response (table_schema cells 접근용)
  missingMaterials,
  mappingResult,        // eslint-disable-line no-unused-vars  (auto matching 카드는 bulkUploadResults로만)
  onMissingChange,      // mapping pipeline 재실행 트리거
  onSupplementalChange, // step2Data.supplementalMaterials 누적 (G-7a R7)
  supplementalMaterials = [], // 업로드 이력 표시용 (G-7a fix)
}) {
  const [textInputOpen, setTextInputOpen] = useState(null)  // missing_id
  const [textInputValue, setTextInputValue] = useState('')
  const [bulkUploadResults, setBulkUploadResults] = useState([])
  const [busy, setBusy] = useState(false)
  const [bulkTargetQid, setBulkTargetQid] = useState('')

  const selected = adaptSelectedQuestion(selectedQid, formData)
  const missingItems = adaptMissingItems(missingMaterials, selectedQid)
  const autoCards = adaptAutoMatchedCards(bulkUploadResults)
  const pendingCards = adaptPendingMatchCards(bulkUploadResults)
  const sufficiency = deriveSufficiency(formData)

  // 2026-05-19 Option C: selectedQid → raw question (table_schema cells 접근용)
  const rawSelectedQuestion = (() => {
    if (!selectedQid || !formApiResp?.sections) return null
    for (const sec of formApiResp.sections) {
      for (const q of (sec.questions || [])) {
        if (q.question_id === selectedQid) return q
      }
    }
    return null
  })()

  // sessionId 없으면 (오프라인) 패널 자체는 표시하되 액션 disabled
  const apiEnabled = !!sessionId

  // 1. 직접 입력
  const submitText = async (missingId) => {
    if (!textInputValue.trim() || !apiEnabled) return
    setBusy(true)
    try {
      const res = await analysisApi.missingText({
        sessionId,
        questionId: selectedQid,
        missingId,
        content: textInputValue.trim(),
      })
      logApi('missing-text raw', {
        supplemental_id: res.supplemental_id,
        status: res.status,
        content_preview: textInputValue.trim().slice(0, 50),
      })
      onSupplementalChange?.({
        supplemental_id: res.supplemental_id,
        question_id: selectedQid,
        missing_id: missingId,
        type: 'text',
        content_preview: textInputValue.trim().slice(0, 50),
        status: res.status || 'uploaded',
      })
      setTextInputOpen(null)
      setTextInputValue('')
      onMissingChange?.()  // mapping 재실행
    } catch (err) {
      handleFallback('missing-text', err)
    } finally {
      setBusy(false)
    }
  }

  // 2. 단일 파일 업로드 (메타만, multipart는 Phase 4-G 후반)
  const submitFile = async (missingId, file) => {
    if (!apiEnabled || !file) return
    setBusy(true)
    try {
      const res = await analysisApi.missingUpload({
        sessionId,
        questionId: selectedQid,
        missingId,
        fileName: file.name,
        fileSizeBytes: file.size,
      })
      logApi('missing-upload raw', {
        file_id: res.file_id,
        supplemental_id: res.supplemental_id,
        file_name: file.name,
      })
      onSupplementalChange?.({
        supplemental_id: res.supplemental_id,
        question_id: selectedQid,
        missing_id: missingId,
        type: 'file',
        file_name: file.name,
        status: res.status || 'uploaded',
      })
      onMissingChange?.()
    } catch (err) {
      handleFallback('missing-upload', err)
    } finally {
      setBusy(false)
    }
  }

  // 3. 일괄 업로드 (다중 파일 메타)
  const submitBulkUpload = async (files) => {
    if (!apiEnabled || !files?.length) return
    setBusy(true)
    try {
      const filesPayload = Array.from(files).map(f => ({
        file_name: f.name,
        file_size_bytes: f.size,
      }))
      const res = await analysisApi.missingBulkUpload({
        sessionId,
        files: filesPayload,
        targetQuestionId: bulkTargetQid || null,
      })
      logApi('missing-bulk-upload raw', {
        total_files: res.total_files,
        auto_matched: res.auto_matched,
        pending: res.pending_user_confirm,
        files: filesPayload.map(f => f.file_name),
      })
      setBulkUploadResults(res.results || [])
      // 각 결과를 supplementalMaterials에 누적
      ;(res.results || []).forEach(r => {
        onSupplementalChange?.({
          supplemental_id: r.supplemental_id,
          question_id: r.target_question_id,
          file_name: r.file_name,
          type: 'file',
          status: r.status || 'uploaded',
          confidence: r.confidence,
          auto_match: r.auto_match,
        })
      })
      onMissingChange?.()
    } catch (err) {
      handleFallback('missing-bulk-upload', err)
    } finally {
      setBusy(false)
    }
  }

  // 4. confirm — 맞음 / 다른 항목 / 제외
  const submitConfirm = async (supplementalId, action, newQuestionId = null) => {
    if (!apiEnabled) return
    setBusy(true)
    try {
      const res = await analysisApi.missingConfirm({
        sessionId,
        supplementalId,
        action,
        newQuestionId,
      })
      logApi('missing-confirm raw', {
        action,
        supplemental_id: supplementalId,
        supplemental_status: res.supplemental_status,
        missing_status: res.missing_status,
      })
      // bulkUploadResults에서 해당 카드 제거 또는 상태 변경
      setBulkUploadResults(prev => prev.filter(r => r.supplemental_id !== supplementalId))
      onSupplementalChange?.({
        supplemental_id: supplementalId,
        status: res.supplemental_status || 'converted',
        _action: action,
      })
      onMissingChange?.()
    } catch (err) {
      handleFallback('missing-confirm', err)
    } finally {
      setBusy(false)
    }
  }

  // 5. AI 다시 검사
  const submitReanalyze = async () => {
    if (!apiEnabled) return
    setBusy(true)
    try {
      const res = await analysisApi.reanalyze({ sessionId, target: 'missing', force: false })
      logApi('reanalyze raw', { status: res.status, affected: res.affected_targets })
      onMissingChange?.()
    } catch (err) {
      handleFallback('reanalyze', err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="bg-white border border-slate-200 rounded-md flex flex-col h-full overflow-hidden">
      {/* 헤더 */}
      <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
        <span className="font-semibold text-slate-900">선택 문항 보완자료</span>
        <button
          onClick={submitReanalyze}
          disabled={busy || !apiEnabled}
          className="text-xs px-2 py-1 border border-slate-200 rounded hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          ↻ AI 다시 검사
        </button>
      </div>

      {/* DEV 영역 — 개발자 모드 + Mock 한계 배너 (J.3=b) */}
      {devMode && (
        <div className="px-3 py-2 border-b border-slate-200 bg-amber-50 text-[10.5px] font-mono text-slate-700">
          <div className="text-[9.5px] uppercase tracking-wider font-semibold mb-1 text-amber-900">
            DEV — API 매핑 + Mock 한계
          </div>
          <div className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 leading-relaxed">
            <span>✎ 직접 입력</span><span className="text-indigo-700">POST /api/analysis/missing/text</span>
            <span>📎 파일 업로드</span><span className="text-indigo-700">POST /api/analysis/missing/upload</span>
            <span>⊕ 일괄 업로드</span><span className="text-indigo-700">POST /api/analysis/missing/bulk-upload</span>
            <span>맞음/다른/제외</span><span className="text-indigo-700">POST /api/analysis/missing/confirm</span>
            <span>↻ AI 다시 검사</span><span className="text-indigo-700">POST /api/analysis/reanalyze</span>
          </div>
          <div className="mt-1.5 text-[10px] text-amber-900 leading-relaxed">
            ⚠ Mock 한계: missing 상태 전이, confidence 추론, evidence 변환은 v0.2.1+ 실제 LLM 시점 검증
          </div>
        </div>
      )}

      <div className="overflow-y-auto flex-1 p-3 space-y-4">
        {/* 1. 선택된 문항 */}
        {selected ? (
          <div>
            <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 mb-1.5">선택 문항</div>
            <div className="border border-slate-200 rounded p-2.5 mb-2">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-slate-500">{selected.qid}</span>
                  <span className="text-sm font-medium text-slate-900">{selected.name}</span>
                </div>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  selected.status === 'missing' ? 'bg-red-50 text-red-700' :
                  selected.status === 'weak' ? 'bg-amber-50 text-amber-700' :
                  'bg-emerald-50 text-emerald-700'
                }`}>
                  {selected.statusLabel}
                </span>
              </div>
            </div>

            {/* 2026-05-19 Option C: 표 항목이면 cell grid 표시 */}
            <SelectedTableCells question={rawSelectedQuestion} />

            {/* 부족자료 목록 (selectedQid 필터) */}
            {missingItems.length > 0 ? (
              <div className="space-y-2">
                {missingItems.map((item) => (
                  <MissingItemCard
                    key={item.id}
                    item={item}
                    busy={busy}
                    apiEnabled={apiEnabled}
                    textInputOpen={textInputOpen}
                    textInputValue={textInputValue}
                    onOpenTextInput={(id) => { setTextInputOpen(id); setTextInputValue('') }}
                    onTextChange={setTextInputValue}
                    onTextSubmit={submitText}
                    onFileSelect={submitFile}
                  />
                ))}
              </div>
            ) : (
              // J.4 — missing 0건 메시지
              <div className="text-xs text-slate-500 italic text-center py-3 border border-dashed border-slate-200 rounded">
                이 문항에 누락된 자료가 없습니다
              </div>
            )}
          </div>
        ) : (
          <div className="text-xs text-slate-400 italic text-center py-4">
            좌측 트리에서 문항을 선택하세요
          </div>
        )}

        {/* 2. 일괄 업로드 (J.2=a, panel 상단 dropzone) */}
        <div className="border-2 border-dashed border-indigo-200 rounded p-3 bg-indigo-50/30">
          <div className="font-semibold text-sm text-slate-900 mb-1">⊕ 부족자료 일괄 업로드</div>
          <div className="text-xs text-slate-600 mb-2 leading-relaxed">
            여러 파일을 한 번에. AI가 자동 분류 (confidence ≥ 0.70 자동 확정).
          </div>
          <label className={`block w-full text-center text-sm px-3 py-2 rounded mb-2 cursor-pointer ${
            busy || !apiEnabled
              ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
              : 'bg-indigo-950 text-white hover:bg-indigo-900'
          }`}>
            📎 파일 선택 (다중 가능)
            <input
              type="file"
              multiple
              hidden
              disabled={busy || !apiEnabled}
              onChange={(e) => submitBulkUpload(e.target.files)}
            />
          </label>
          <div className="border-t border-indigo-200 pt-2">
            <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 mb-1">
              해당 항목 지정 <span className="text-[9px] text-slate-400 normal-case tracking-normal ml-1">(선택)</span>
            </div>
            <input
              value={bulkTargetQid}
              onChange={(e) => setBulkTargetQid(e.target.value)}
              placeholder="예: IV-2 (비워두면 AI 자동 분류)"
              className="w-full text-[11px] px-2 py-1 border border-slate-200 rounded"
            />
          </div>
          <div className="text-[10px] text-slate-500 italic mt-2">
            ⓘ v0.2: 파일 메타만 처리. 실제 multipart 업로드는 Phase 4-G 후반에서.
          </div>
        </div>

        {/* 3. AI 자동 매칭 — bulkUploadResults에서 동적 생성 (J.1=b') */}
        {autoCards.length > 0 && (
          <MatchResultSection
            title="AI 매칭 결과 — 자동 확정"
            cards={autoCards}
            type="auto"
            onConfirm={submitConfirm}
            busy={busy}
          />
        )}

        {/* 4. 사용자 확인 필요 — bulkUploadResults pending */}
        {pendingCards.length > 0 && (
          <MatchResultSection
            title="AI 매칭 결과 — 사용자 확인 필요"
            cards={pendingCards}
            type="pending"
            onConfirm={submitConfirm}
            busy={busy}
          />
        )}

        {/* 5. 업로드 이력 (supplementalMaterials 누적 — confirm 후에도 유지) */}
        {supplementalMaterials.length > 0 && (
          <div className="border border-slate-200 rounded p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">
                업로드 이력
              </span>
              <span className="text-[10px] text-slate-500 font-mono">{supplementalMaterials.length}건</span>
            </div>
            <div className="space-y-1.5">
              {supplementalMaterials.map((s, i) => (
                <div key={s.supplemental_id || i} className="flex items-center gap-2 text-xs">
                  <span className="text-[11px] shrink-0">{s.type === 'text' ? '✎' : '📎'}</span>
                  <span
                    className="text-slate-900 flex-1 min-w-0 truncate"
                    title={s.file_name || s.content_preview || s.supplemental_id}
                  >
                    {s.file_name || s.content_preview || '(이름 없음)'}
                  </span>
                  {s.question_id && (
                    <span className="font-mono text-[10px] text-slate-500 shrink-0">
                      {s.question_id}
                    </span>
                  )}
                  <span className={`text-[10px] px-1.5 py-0.5 rounded shrink-0 ${
                    s.status === 'converted' ? 'bg-emerald-50 text-emerald-700' :
                    s.status === 'analyzed' ? 'bg-blue-50 text-blue-700' :
                    s.status === 'uploaded' ? 'bg-slate-100 text-slate-600' :
                    s.status === 'failed' ? 'bg-red-50 text-red-700' :
                    'bg-slate-100 text-slate-600'
                  }`}>
                    {s.status || 'uploaded'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 6. 전체 충족도 */}
        <div className="border border-slate-200 rounded p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-slate-700">전체 자료 충족도</span>
            <span className="text-sm font-mono">
              <span className="text-slate-900 font-semibold">{sufficiency.ok}</span>
              <span className="text-slate-400 mx-0.5">/</span>
              <span className="text-slate-600">{sufficiency.total}</span>
              <span className="ml-2 text-emerald-700 font-semibold">{sufficiency.percent}%</span>
            </span>
          </div>
          <div className="h-2 bg-slate-100 rounded overflow-hidden mb-2">
            <div
              className="h-full bg-emerald-500"
              style={{ width: `${sufficiency.percent}%` }}
            />
          </div>
          <div className="flex gap-3 text-[11px] text-slate-600">
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              작성가능 {sufficiency.ok}
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-amber-500" />
              근거부족 {sufficiency.weak}
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-red-500" />
              자료없음 {sufficiency.missing}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── 개별 부족자료 카드 ───
function MissingItemCard({ item, busy, apiEnabled, textInputOpen, textInputValue, onOpenTextInput, onTextChange, onTextSubmit, onFileSelect }) {
  const isInputOpen = textInputOpen === item.id

  return (
    <div className="border border-slate-200 rounded p-2.5">
      <div className="text-sm text-slate-900 font-medium mb-0.5">{item.label}</div>
      <div className="text-xs text-slate-500 mb-2">{item.desc}</div>
      <div className="flex flex-wrap gap-1">
        {item.actions.map((act) => (
          <button
            key={act}
            disabled={busy || !apiEnabled}
            onClick={() => {
              if (act === '직접입력') onOpenTextInput(item.id)
              else if (act === '파일업로드') document.getElementById(`file-${item.id}`)?.click()
              // 원문보기 / 나중에 — UI only
            }}
            className={`text-[11px] px-2 py-1 rounded transition disabled:opacity-50 disabled:cursor-not-allowed ${ITEM_BTN_STYLE[act]}`}
          >
            {ITEM_BTN_ICON[act]} {act}
          </button>
        ))}
        <input
          id={`file-${item.id}`}
          type="file"
          hidden
          onChange={(e) => onFileSelect(item.id, e.target.files?.[0])}
        />
      </div>
      {isInputOpen && (
        <div className="mt-2 space-y-1.5">
          <textarea
            value={textInputValue}
            onChange={(e) => onTextChange(e.target.value)}
            placeholder="직접 입력할 내용..."
            className="w-full text-xs p-2 border border-slate-200 rounded min-h-[80px] resize-none"
          />
          <div className="flex gap-1.5">
            <button
              disabled={busy || !textInputValue.trim()}
              onClick={() => onTextSubmit(item.id)}
              className="text-[11px] px-3 py-1 bg-indigo-950 text-white rounded hover:bg-indigo-900 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {busy ? '저장 중...' : '저장'}
            </button>
            <button
              onClick={() => onOpenTextInput(null)}
              className="text-[11px] px-3 py-1 border border-slate-200 rounded hover:bg-slate-50"
            >
              취소
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── AI 매칭 결과 섹션 ───
function MatchResultSection({ title, cards, type, onConfirm, busy }) {
  return (
    <div className="border border-slate-200 rounded overflow-hidden">
      <div className="px-3 py-2 border-b border-slate-200 flex items-center justify-between">
        <div className="text-sm font-semibold text-slate-900">{title}</div>
        <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${
          type === 'pending' ? 'bg-amber-50 text-amber-900' : 'bg-emerald-50 text-emerald-900'
        }`}>
          {cards.length}건
        </span>
      </div>
      <div className="divide-y divide-slate-100">
        {cards.map((card) => (
          <MatchCard key={card.supplemental_id} card={card} type={type} onConfirm={onConfirm} busy={busy} />
        ))}
      </div>
    </div>
  )
}

function MatchCard({ card, type, onConfirm, busy }) {
  const confColor = card.confLevel === 'high' ? 'text-emerald-700' : card.confLevel === 'mid' ? 'text-amber-700' : 'text-red-700'
  return (
    <div className="px-3 py-2.5">
      <div className="flex items-center gap-1.5 mb-1">
        <span className="font-mono text-xs text-slate-500">{card.qid || '?'}</span>
        <span className="text-sm font-medium text-slate-900">{card.file}</span>
        {card.confidence != null && (
          <span className={`text-xs font-semibold ${confColor}`}>{card.confidence}%</span>
        )}
      </div>
      {card.tag && <div className="text-[11px] text-emerald-700 font-medium mb-1">{card.tag}</div>}
      {card.desc && <div className="text-xs text-slate-600 mb-1.5">{card.desc}</div>}
      {type === 'pending' && (
        <div className="flex gap-1.5 mt-1.5">
          <button
            disabled={busy}
            onClick={() => onConfirm(card.supplemental_id, 'correct')}
            className="text-[11px] px-2 py-1 bg-indigo-950 text-white rounded hover:bg-indigo-900 disabled:opacity-50"
          >
            ✓ 맞음
          </button>
          <button
            disabled={busy}
            onClick={() => {
              const newQid = prompt('어느 문항으로 재매핑할까요? (예: III-1)', card.qid)
              if (newQid) onConfirm(card.supplemental_id, 'different', newQid)
            }}
            className="text-[11px] px-2 py-1 bg-white border border-slate-200 rounded hover:bg-slate-50 disabled:opacity-50"
          >
            ↔ 다른 항목
          </button>
          <button
            disabled={busy}
            onClick={() => onConfirm(card.supplemental_id, 'exclude')}
            className="text-[11px] px-2 py-1 text-slate-500 rounded hover:bg-slate-50 disabled:opacity-50"
          >
            ✗ 제외
          </button>
        </div>
      )}
    </div>
  )
}

// 2026-05-19 Option C: 선택된 표 항목의 cell grid 표시.
// table_schema.header_cells + data_rows (layout-derived) 우선, 없으면 columns 폴백.
function SelectedTableCells({ question }) {
  if (!question) return null
  const isTable = question.is_table_item || question.fill_mode === 'table_input'
  if (!isTable) return null

  const ts = question.table_schema || {}
  const headerCells = Array.isArray(ts.header_cells) ? ts.header_cells : []
  const dataRows = Array.isArray(ts.data_rows) ? ts.data_rows : []
  const hasLayoutCells = headerCells.length > 0 || dataRows.length > 0
  const columns = Array.isArray(ts.columns) ? ts.columns : []
  const colCount = hasLayoutCells
    ? (headerCells[0]?.length || dataRows[0]?.cells?.length || columns.length)
    : columns.length

  return (
    <div className="mb-3 border border-slate-300 rounded overflow-hidden bg-white">
      <div className="bg-slate-100 px-2.5 py-1.5 text-[10px] font-semibold text-slate-700 flex items-center justify-between">
        <span>
          📊 표 구조 ({colCount}열 × {hasLayoutCells ? dataRows.length : 0}행)
        </span>
        {hasLayoutCells
          ? <span className="text-[9px] text-emerald-700 font-normal">· layout cells</span>
          : <span className="text-[9px] text-amber-700 font-normal">· columns only (no cells)</span>}
      </div>
      <div className="overflow-x-auto max-h-[300px] overflow-y-auto">
        <table className="w-full text-[10.5px] border-collapse">
          {hasLayoutCells ? (
            <>
              <thead className="bg-slate-50 sticky top-0">
                {headerCells.map((row, ri) => (
                  <tr key={ri}>
                    {row.map((cell) => (
                      <th
                        key={cell.cell_id}
                        title={cell.cell_id}
                        className="px-1.5 py-1 text-left font-medium text-slate-700 border border-slate-200"
                      >
                        {cell.text || <span className="text-slate-300">·</span>}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {dataRows.length === 0 ? (
                  <tr>
                    <td colSpan={colCount} className="px-2 py-2 text-center text-slate-400 italic border border-slate-200">
                      (data row 없음 — header만 추출됨)
                    </td>
                  </tr>
                ) : (
                  dataRows.map((row) => (
                    <tr key={row.row_id} className="hover:bg-slate-50/50">
                      {(row.cells || []).map((cell) => (
                        <td
                          key={cell.cell_id}
                          title={cell.cell_id}
                          className={`px-1.5 py-1 border border-slate-200 ${
                            cell.is_empty ? 'bg-amber-50/40 text-slate-400 italic' : 'text-slate-800'
                          }`}
                        >
                          {cell.text || '(빈 cell)'}
                        </td>
                      ))}
                    </tr>
                  ))
                )}
              </tbody>
            </>
          ) : columns.length > 0 ? (
            <thead className="bg-slate-50">
              <tr>
                {columns.map((c, i) => (
                  <th key={i} className="px-1.5 py-1 text-left font-medium text-slate-700 border border-slate-200">
                    {(c.header_path?.[0]) || c.name || `c${i + 1}`}
                  </th>
                ))}
              </tr>
            </thead>
          ) : (
            <tbody>
              <tr>
                <td className="px-2 py-2 text-center text-slate-400 italic">
                  (표 구조 정보 없음)
                </td>
              </tr>
            </tbody>
          )}
        </table>
      </div>
    </div>
  )
}
