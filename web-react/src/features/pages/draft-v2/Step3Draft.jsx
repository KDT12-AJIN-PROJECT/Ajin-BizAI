// AJIN BizAI v0.2 — Step 3: AI 초안 작성
// 출처: PRD §10 / §19.4 / test_06 §6.7 draft_writer (환각 방지 5가지)
// 구조: 좌(트리) / 중(작성영역) / 우(AI 보완 패널)
//
// Phase 4-G-6: write-draft-item / rewrite-draft-item / approve-draft-item / chat/draft-assist API 통합
//   - DraftPageV2에서 step2Data (formApiResp, mappingResult, companyData, noticeApiResp) 받아옴
//   - sessionId 없거나 step2Data 없으면 DRAFT_MOCK + FORM_MOCK fallback

import { useState, useEffect } from 'react'
import { analysisApi, chatApi } from '../../../api/backendApi'
import { USE_MOCK } from '../../../config/env'
import { logApi, handleFallback } from '../../../lib/runtimeLog'
import FormTreePanel, { FORM_MOCK } from './shared/FormTreePanel'
import SupplementalPanel from './shared/SupplementalPanel'
import StepNavigationBar from './components/StepNavigationBar'
// 2026-05-18: mappingResult + missingMaterials를 question status로 적용 (E-2 vector RAG 결과 시각화)
import { applyStatusToForm } from './Step2Analysis'

// ─── Mock Draft Data (PRD §13.7 DraftItem) ───
const DRAFT_MOCK = {
  'I-1': { content: '아진산업㈜는 2018년 설립된 제조 데이터 분석 전문기업으로, 자체 개발한 PMS-AI 플랫폼을 통해 4개 제조 라인에 적용 중입니다.\n\n2025년 누적 매출 142억 원, 영업이익률 11.4%, 직전 3년 매출 CAGR 18.6% 달성하였으며, 중기부 R&D 사업 2건과 산업부 스마트공장 보급사업 1건을 성공적으로 수행한 이력을 보유하고 있습니다.', maxLength: 800, status: 'generated', evidenceIds: ['ev_001', 'ev_005'] },
  'I-2': { content: '주요 제품 PMS-AI는 공정 데이터 기반 불량 원인 분석 및 예측 모델...', maxLength: 1000, status: 'generated', evidenceIds: ['ev_002'] },
  'I-3': { content: '', maxLength: 1200, status: 'draft', evidenceIds: [] },
  'II-1': { content: '국내 제조업의 디지털 전환 시장은 2024년 기준 연 18.4% 성장률을 기록하고 있으나...\n\n[사용자 확인 필요] 시장 규모 정량 데이터 보강 권장.', maxLength: 1500, status: 'needs_revision', warnings: ['시장 규모 정량 데이터 부족'], evidenceIds: ['ev_010'] },
  'II-2': { content: '', maxLength: 1000, status: 'blocked', blocked: true, reason: '자료 없음 — AI 자동 작성 차단됨. 사용자 직접 작성 필요.' },
  'III-T1': { content: '추진 일정표 (mock 표 데이터)', maxLength: null, status: 'generated', tableData: true },
  'III-1': { content: '', maxLength: 2000, status: 'draft', evidenceIds: [] },
  'III-2': { content: '', maxLength: 1500, status: 'draft', evidenceIds: [] },
  'IV-1': { content: '', maxLength: null, status: 'draft', tableData: true },
  'IV-2': { content: '', maxLength: 1500, status: 'draft', evidenceIds: [] },
  'V-1': { content: '', maxLength: 1000, status: 'draft', evidenceIds: [] },
  'V-2': { content: '', maxLength: 800, status: 'draft', evidenceIds: [] },
  'V-3': { content: '', maxLength: 600, status: 'draft', evidenceIds: [] },
}

// ─── Mock Chat Messages ───
const CHAT_INIT = [
  { role: 'ai', text: '문항 II-1 시장 문제 작성을 도와드립니다. "더 정량적으로", "경쟁사 비교 추가" 같은 요청이 가능합니다.' },
]

function findQuestion(qid, formData) {
  const src = formData || FORM_MOCK
  for (const sec of src.sections) {
    const q = sec.questions.find((x) => x.id === qid)
    if (q) return { ...q, sectionTitle: sec.title }
  }
  return null
}

// step2Data.formApiResp의 sections에서 raw question 찾기 (write-draft-item용)
function findRawQuestion(qid, formApiResp) {
  if (!formApiResp?.sections) return null
  for (const sec of formApiResp.sections) {
    const q = (sec.questions || []).find(x => (x.question_id || x.id) === qid)
    if (q) return q
  }
  return null
}

// mappingResult에서 question_id에 매칭된 evidence 찾기
function findMatchedEvidence(qid, mappingResult, evidenceData) {
  if (!mappingResult?.question_mappings) return []
  const mapping = mappingResult.question_mappings.find(m => m.question_id === qid)
  if (!mapping) return []
  const evidenceIds = mapping.used_evidence_ids || mapping.matched_evidence_ids || []
  const allEvidence = evidenceData?.items || []
  return allEvidence.filter(e => evidenceIds.includes(e.evidence_id))
}

const STATUS_LABEL = {
  draft: { label: '초안 없음', cls: 'bg-slate-100 text-slate-600' },
  generating: { label: '생성 중...', cls: 'bg-blue-50 text-blue-600 animate-pulse' },
  generated: { label: '생성됨', cls: 'bg-emerald-50 text-emerald-700' },
  user_edited: { label: '편집됨', cls: 'bg-blue-50 text-blue-700' },
  needs_revision: { label: '검토 필요', cls: 'bg-amber-50 text-amber-700' },
  approved: { label: '승인됨', cls: 'bg-emerald-100 text-emerald-800 font-semibold' },
  blocked: { label: 'AI 작성 차단', cls: 'bg-red-50 text-red-700' },
}

export default function Step3Draft({
  onPrev, onNext, sessionId, step2Data, notice,
  drafts: draftsProp,                  // Phase 4-G-7b: lift up from DraftPageV2
  onDraftsChange,
  selectedQid: selectedQidProp,
  onSelectQid,
  supplementalMaterials = [],          // C-5c: DraftPageV2 lift-up state
  onSupplementalChange,                // C-5c: dedupe upsert callback (DraftPageV2)
}) {
  // step2Data가 있으면 formData/formApiResp/mappingResult 등 활용
  const rawFormData = step2Data?.formData || FORM_MOCK
  const formApiResp = step2Data?.formApiResp
  const noticeApiResp = step2Data?.noticeApiResp
  const mappingResult = step2Data?.mappingResult
  const companyData = step2Data?.companyData
  const evidenceData = step2Data?.evidenceData
  const missingMaterials = step2Data?.missingMaterials
  // 2026-05-18: excluded 항목도 status='excluded'로 표시
  const excludedIds = formApiResp?.excluded_question_ids || rawFormData?.excluded_question_ids || []
  const formData = (mappingResult || missingMaterials || excludedIds.length > 0)
    ? applyStatusToForm(rawFormData, mappingResult, missingMaterials, excludedIds)
    : rawFormData
  // isExcluded는 selectedQid 정의 후 계산 (TDZ 회피)

  // v3.2 C-5c Q1: DRAFT_MOCK fallback은 USE_MOCK=true일 때만.
  //   USE_MOCK=false (default/production): backend 빈 응답이어도 그대로 빈 표시.
  //   USE_MOCK=true: 데모 시나리오에서 DRAFT_MOCK으로 시각화 보강.
  //   M-0 정책: legacyDraftsApi 호출 금지 — 본 컴포넌트는 analysisApi만 사용.
  const hasRealForm = !!formApiResp
  const draftsInternal = draftsProp ?? (USE_MOCK && !hasRealForm ? DRAFT_MOCK : {})
  // hasRealForm: 실제 양식이면 mock merge 금지 (의미 다름)
  // USE_MOCK=true && !hasRealForm: 데모 fallback
  const drafts = (USE_MOCK && !hasRealForm)
    ? { ...DRAFT_MOCK, ...draftsInternal }
    : draftsInternal

  // selectedQid 기본값: prop > (실제 양식이면 첫 question / USE_MOCK이면 DRAFT_MOCK 첫 키)
  const firstRealQid =
    formApiResp?.sections?.[0]?.questions?.[0]?.question_id ||
    formApiResp?.sections?.[0]?.questions?.[0]?.id
  const selectedQid =
    selectedQidProp
    ?? (hasRealForm ? firstRealQid : (USE_MOCK ? Object.keys(DRAFT_MOCK)[0] : null))
    ?? 'I-1'
  const setSelectedQid = onSelectQid || (() => {})
  // 2026-05-18: excluded 체크 (selectedQid 정의 후)
  const isExcluded = excludedIds.includes(selectedQid)

  // drafts 업데이트는 controlled callback (USE_MOCK=true && !hasRealForm일 때만 mock merge)
  const setDrafts = (updater) => {
    if (!onDraftsChange) return
    if (typeof updater === 'function') {
      onDraftsChange(prev => updater(
        (USE_MOCK && !hasRealForm) ? { ...DRAFT_MOCK, ...prev } : (prev || {})
      ))
    } else {
      onDraftsChange(updater)
    }
  }

  const [chat, setChat] = useState(CHAT_INIT)
  const [chatInput, setChatInput] = useState('')
  const [busy, setBusy] = useState({})  // {[qid]: 'generating' | 'approving' | 'rewriting'} | global 'chat'

  // C-5c: missingMaterials client-side resolve 마킹 (옵션 B — _clientResolved + status='resolved')
  // backend 상태 변경 없음. 새로고침 시 step2Data.missingMaterials로부터 다시 sync.
  const [localMissingMaterials, setLocalMissingMaterials] = useState([])
  useEffect(() => {
    setLocalMissingMaterials(step2Data?.missingMaterials || [])
  }, [step2Data?.missingMaterials])

  // C-5c: 우측 패널 탭 (보완자료 | AI 챗봇)
  // touched gate: 사용자가 직접 클릭 전에는 selectedQid 변경 시 자동 추천
  const [rightTab, setRightTab] = useState('chat')
  const [rightTabTouched, setRightTabTouched] = useState(false)
  useEffect(() => {
    if (rightTabTouched) return
    const hasMissing = (localMissingMaterials || []).some(
      m => m.question_id === selectedQid && m.status !== 'resolved' && m.status !== 'rejected'
    )
    setRightTab(hasMissing ? 'supplemental' : 'chat')
  }, [selectedQid, localMissingMaterials, rightTabTouched])

  const handleRightTabChange = (tab) => {
    setRightTab(tab)
    setRightTabTouched(true)
  }

  // C-5c: SupplementalPanel.onSupplementalChange wrapper
  // 1. DraftPageV2 dedupe upsert에 위임
  // 2. item.missing_id 있으면 local에서 client-resolve 마킹 (옵션 B)
  const wrappedSupplementalChange = (item) => {
    onSupplementalChange?.(item)
    if (item?.missing_id) {
      setLocalMissingMaterials(prev =>
        prev.map(m =>
          m.missing_id === item.missing_id
            ? { ...m, status: 'resolved', _clientResolved: true }
            : m
        )
      )
    }
  }

  // 미해결 missing count (선택 문항 기준) — 탭 배지
  const currentMissingCount = (localMissingMaterials || []).filter(
    m => m.question_id === selectedQid && m.status !== 'resolved' && m.status !== 'rejected'
  ).length

  const q = findQuestion(selectedQid, formData)
  const draft = drafts[selectedQid] || { content: '', maxLength: 1000, status: 'draft' }
  const charCount = draft.content?.length || 0
  const overLimit = draft.maxLength && charCount > draft.maxLength
  const isBusy = !!busy[selectedQid]

  const handleEdit = (newContent) => {
    setDrafts((prev) => ({
      ...prev,
      [selectedQid]: { ...prev[selectedQid], content: newContent, status: 'user_edited' },
    }))
  }

  const handleGenerate = async () => {
    if (!sessionId) {
      setDrafts((prev) => ({
        ...prev,
        [selectedQid]: { ...prev[selectedQid], content: `[mock — ${q?.title}]\n\n${prev[selectedQid]?.content || ''}`, status: 'generated' },
      }))
      return
    }
    const rawQ = findRawQuestion(selectedQid, formApiResp)
    const question = rawQ || { question_id: selectedQid, title: q?.title || '', constraints: { max_length: draft.maxLength || 1000 } }
    const matchedEvidence = findMatchedEvidence(selectedQid, mappingResult, evidenceData)

    setBusy(b => ({ ...b, [selectedQid]: 'generating' }))
    // 초기 상태: 빈 content로 'generating' 표시
    setDrafts(prev => ({ ...prev, [selectedQid]: { ...prev[selectedQid], content: '', status: 'generating' } }))
    try {
      const res = await analysisApi.writeDraftItemStream({
        sessionId, question, matchedEvidence,
        companySchema: companyData?.company || {},
        noticeSchema: noticeApiResp || {},
        constraints: question.constraints,
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let accumulated = ''
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() // 마지막 incomplete line 보존
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6).trim()
          if (data === '[DONE]') break
          try {
            const parsed = JSON.parse(data)
            if (parsed.error) throw new Error(parsed.error)
            if (parsed.delta) {
              accumulated += parsed.delta
              setDrafts(prev => ({
                ...prev,
                [selectedQid]: { ...prev[selectedQid], content: accumulated, status: 'generating' },
              }))
            }
          } catch (parseErr) { /* skip malformed chunk */ }
        }
      }
      const evidenceIds = matchedEvidence.map(e => e.evidence_id).filter(Boolean)
      setDrafts(prev => ({
        ...prev,
        [selectedQid]: { ...prev[selectedQid], content: accumulated, status: 'generated', evidenceIds },
      }))
    } catch (err) {
      handleFallback('write-draft-item', err)
      setDrafts(prev => ({
        ...prev,
        [selectedQid]: { ...prev[selectedQid], content: `[생성 실패] ${err.message}`, status: 'draft' },
      }))
    } finally {
      setBusy(b => { const n = { ...b }; delete n[selectedQid]; return n })
    }
  }

  const handleApprove = async () => {
    if (!sessionId) {
      setDrafts(prev => ({ ...prev, [selectedQid]: { ...prev[selectedQid], status: 'approved' } }))
      return
    }
    setBusy(b => ({ ...b, [selectedQid]: 'approving' }))
    try {
      const res = await analysisApi.approveDraftItem({
        sessionId,
        questionId: selectedQid,
        draftItemId: draft.draftItemId || null,
      })
      logApi('approve-draft-item raw', { status: res.status, lock_on_reanalyze: res.lock_on_reanalyze })
      setDrafts(prev => ({ ...prev, [selectedQid]: { ...prev[selectedQid], status: 'approved' } }))
    } catch (err) {
      handleFallback('approve-draft-item', err)
    } finally {
      setBusy(b => { const n = { ...b }; delete n[selectedQid]; return n })
    }
  }

  const handleSendChat = async () => {
    const msg = chatInput.trim()
    if (!msg) return
    setChat((c) => [...c, { role: 'user', text: msg }])
    setChatInput('')

    if (!sessionId) {
      setChat((c) => [...c, { role: 'ai', text: `[AI 응답 mock] "${msg}" 반영하여 수정 제안: ...` }])
      return
    }
    setBusy(b => ({ ...b, _chat: true }))
    try {
      const res = await chatApi.draftAssist({
        sessionId,
        questionId: selectedQid,
        message: msg,
        draftContent: draft.content || '',
        noticeTitle: notice?.title || '',
        history: chat.slice(-6).map(m => ({ role: m.role === 'ai' ? 'assistant' : 'user', content: m.text })),
      })
      logApi('chat/draft-assist raw', {
        response_len: (res.response || '').length,
        history_appended: res.history_appended?.length || 0,
      })
      setChat((c) => [...c, { role: 'ai', text: res.response || '(응답 없음)' }])
    } catch (err) {
      handleFallback('chat/draft-assist', err)
      setChat((c) => [...c, { role: 'ai', text: `[chat 실패] ${err.message}` }])
    } finally {
      setBusy(b => { const n = { ...b }; delete n._chat; return n })
    }
  }

  // 사용자가 chat 응답을 "적용"하면 rewrite-draft-item 호출 — 마지막 사용자 메시지를 user_message로 사용
  const handleApplyRewrite = async (suggestedText) => {
    if (!sessionId) {
      setDrafts(prev => ({ ...prev, [selectedQid]: { ...prev[selectedQid], content: suggestedText, status: 'user_edited' } }))
      return
    }
    const lastUserMsg = [...chat].reverse().find(m => m.role === 'user')?.text || ''
    setBusy(b => ({ ...b, [selectedQid]: 'rewriting' }))
    try {
      const res = await analysisApi.rewriteDraftItem({
        sessionId,
        questionId: selectedQid,
        currentDraft: draft.content || '',
        userMessage: lastUserMsg,
        evidenceList: evidenceData?.items || [],
      })
      logApi('rewrite-draft-item raw', {
        draft_item_id: res.draft_item_id,
        version: res.version,
        has_suggestion: !!(res.result?.suggestion || res.result?.content),
      })
      const content = res.result?.suggestion || res.result?.content || suggestedText
      setDrafts(prev => ({
        ...prev,
        [selectedQid]: { ...prev[selectedQid], content, status: 'user_edited' },
      }))
    } catch (err) {
      handleFallback('rewrite-draft-item', err)
    } finally {
      setBusy(b => { const n = { ...b }; delete n[selectedQid]; return n })
    }
  }

  return (
    <div className="p-6">
      <div className="mb-4">
        <h2 className="text-2xl font-bold text-slate-900">Step 3. AI 초안 작성</h2>
        <p className="text-sm text-slate-500 mt-1">
          좌측에서 문항 선택 → 중앙 작성 영역 → 우측 AI 보완 (대화형)
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr_360px] gap-3 h-[calc(100vh-280px)] min-h-[500px]">
        {/* 좌: 항목 트리 (재사용) */}
        <FormTreePanel selectedQid={selectedQid} onSelect={setSelectedQid} formData={formData} />

        {/* 중: 작성 영역 */}
        <div className="bg-white border border-slate-200 rounded-md flex flex-col overflow-hidden">
          {q && (
            <div className="px-4 py-3 border-b border-slate-200">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-slate-500">{q.id}</span>
                  <span className="font-semibold text-slate-900">{q.title}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${(STATUS_LABEL[draft.status] || STATUS_LABEL.draft).cls}`}>
                    {(STATUS_LABEL[draft.status] || STATUS_LABEL.draft).label}
                  </span>
                  {draft.maxLength && (
                    <span className={`text-xs font-mono ${overLimit ? 'text-red-700 font-semibold' : 'text-slate-500'}`}>
                      {charCount} / {draft.maxLength}
                    </span>
                  )}
                </div>
              </div>
              <div className="text-xs text-slate-500">
                {q.sectionTitle} · {q.meta.join(' · ')}
              </div>
            </div>
          )}

          <div className="flex-1 overflow-y-auto p-4">
            {draft.blocked ? (
              <div className="bg-red-50 border border-red-200 rounded p-4 text-sm">
                <div className="font-semibold text-red-900 mb-1">🚫 AI 자동 작성 차단</div>
                <div className="text-red-800 mb-2">{draft.reason}</div>
                <div className="text-xs text-red-700">
                  PRD §14.3 환각 방지 #3 — 자료 없음 문항은 AI 자동 작성을 차단합니다.
                  <br />
                  사용자가 직접 작성하시거나 부족자료를 보완해주세요.
                </div>
                <textarea
                  value={draft.content || ''}
                  onChange={(e) => handleEdit(e.target.value)}
                  placeholder="여기에 직접 작성..."
                  className="w-full mt-3 p-3 border border-red-200 rounded text-sm leading-relaxed min-h-[200px] resize-none"
                />
              </div>
            ) : isExcluded ? (
              // 2026-05-18: 사용자가 "작성 제외"로 표시한 항목
              <div className="bg-slate-50 border border-slate-300 rounded p-4 text-sm">
                <div className="font-semibold text-slate-700 mb-1">🚫 작성 제외됨</div>
                <div className="text-slate-600 mb-3">
                  이 항목은 "작성 제외"로 표시되어 있습니다. 매핑/AI 초안 작성에서 제외되며,
                  작성 항목 카운트에서도 빠집니다. 필요하면 트리에서 ↺ 제외 해제 또는 직접 작성 가능합니다.
                </div>
                <textarea
                  value={draft.content || ''}
                  onChange={(e) => handleEdit(e.target.value)}
                  placeholder="(선택) 직접 작성하려면 여기 입력. 비워두면 export 시에도 빈 채로 포함됨."
                  className="w-full p-3 border border-slate-200 rounded text-sm leading-relaxed min-h-[150px] resize-none bg-white"
                />
              </div>
            ) : (
              <>
                {draft.warnings && draft.warnings.length > 0 && (
                  <div className="mb-3 p-2.5 bg-amber-50 border border-amber-200 rounded text-xs text-amber-900">
                    ⚠ {draft.warnings.join(' / ')}
                  </div>
                )}
                {/* 2026-05-18: table_input 항목용 표 grid */}
                {/* 2026-05-19 Option C: table_schema.header_cells + data_rows 우선 사용 (layout-derived) */}
                {(() => {
                  const rawQ = findRawQuestion(selectedQid, formApiResp)
                  const isTable = rawQ?.is_table_item || rawQ?.fill_mode === 'table_input'
                  if (!isTable) return null

                  const ts = rawQ?.table_schema || {}
                  const headerCells = Array.isArray(ts.header_cells) ? ts.header_cells : []
                  const dataRows = Array.isArray(ts.data_rows) ? ts.data_rows : []
                  const hasLayoutCells = headerCells.length > 0 || dataRows.length > 0

                  // 컬럼 폴백 (layout cells 없을 때 — LLM-only path)
                  const oldCols = Array.isArray(rawQ?.table_columns) ? rawQ.table_columns : []
                  const newCols = (ts.columns || []).map(c => (c.header_path?.[0]) || c.name || c.field_id || '')
                  const cols = oldCols.length ? oldCols.map(c => typeof c === 'string' ? c : (c?.name || '')) : newCols
                  const tableData = Array.isArray(draft.tableData) ? draft.tableData : []
                  const colCount = hasLayoutCells
                    ? (headerCells[0]?.length || dataRows[0]?.cells?.length || cols.length)
                    : cols.length

                  return (
                    <div className="mb-4 border border-slate-300 rounded overflow-hidden">
                      <div className="bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-700 flex items-center justify-between">
                        <span>
                          📊 표 데이터 ({colCount}열 × {hasLayoutCells ? dataRows.length : tableData.length}행)
                          {hasLayoutCells && <span className="ml-2 text-[10px] text-emerald-700 font-normal">· layout cells</span>}
                        </span>
                        {!hasLayoutCells && tableData.length === 0 && (
                          <span className="text-slate-400">[AI 초안 생성] 클릭 시 표 데이터 생성됨</span>
                        )}
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs border-collapse">
                          {hasLayoutCells ? (
                            <>
                              <thead className="bg-slate-50">
                                {headerCells.map((row, ri) => (
                                  <tr key={ri}>
                                    {row.map((cell) => (
                                      <th
                                        key={cell.cell_id}
                                        title={cell.cell_id}
                                        className="px-2 py-1.5 text-left font-medium text-slate-700 border border-slate-200"
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
                                    <td colSpan={colCount} className="px-2 py-3 text-center text-slate-400 italic border border-slate-200">
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
                                          className={`px-2 py-1.5 border border-slate-200 ${cell.is_empty ? 'bg-amber-50/30 text-slate-400' : 'text-slate-800'}`}
                                        >
                                          {cell.text || <span className="italic text-slate-300">(빈 cell)</span>}
                                        </td>
                                      ))}
                                    </tr>
                                  ))
                                )}
                              </tbody>
                            </>
                          ) : (
                            <>
                              <thead className="bg-slate-50">
                                <tr>
                                  {cols.map((c, i) => (
                                    <th key={i} className="px-2 py-1.5 text-left font-medium text-slate-700 border-b border-slate-200">
                                      {c}
                                    </th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {tableData.length === 0 ? (
                                  <tr>
                                    <td colSpan={cols.length || 1} className="px-2 py-3 text-center text-slate-400 italic">
                                      (표 데이터 없음 — AI 초안 생성 시 자동 채워짐)
                                    </td>
                                  </tr>
                                ) : (
                                  tableData.map((row, ri) => (
                                    <tr key={ri} className="border-b border-slate-100 hover:bg-slate-50/50">
                                      {Array.isArray(row) ? row.map((cell, ci) => (
                                        <td key={ci} className="px-2 py-1.5 text-slate-800">
                                          {cell ?? ''}
                                        </td>
                                      )) : (
                                        <td colSpan={cols.length} className="px-2 py-1.5 text-red-600 text-[10px]">
                                          ⚠ row 형식 오류 (list 아님)
                                        </td>
                                      )}
                                    </tr>
                                  ))
                                )}
                              </tbody>
                            </>
                          )}
                        </table>
                      </div>
                    </div>
                  )
                })()}
                <textarea
                  value={draft.content || ''}
                  onChange={(e) => handleEdit(e.target.value)}
                  placeholder={`${q?.title || '문항'} 에 대한 초안을 작성하거나 [AI 초안 생성] 버튼을 누르세요`}
                  className={`w-full p-3 border rounded text-sm leading-relaxed min-h-[300px] resize-none ${
                    overLimit ? 'border-red-300 bg-red-50/30' : 'border-slate-200'
                  }`}
                />
                {draft.evidenceIds && draft.evidenceIds.length > 0 && (
                  <div className="mt-3 text-xs text-slate-500">
                    <span className="font-semibold">사용된 evidence:</span>{' '}
                    {draft.evidenceIds.map((id) => (
                      <span key={id} className="font-mono mx-1 px-1.5 py-0.5 bg-indigo-50 text-indigo-900 rounded">
                        {id}
                      </span>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          {!draft.blocked && (
            <div className="px-4 py-3 border-t border-slate-200 flex flex-wrap gap-2">
              <button
                onClick={handleGenerate}
                disabled={isBusy}
                className="text-xs px-3 py-1.5 bg-indigo-950 text-white rounded hover:bg-indigo-900 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {busy[selectedQid] === 'generating' ? '⚙ 생성 중...' : '⚙ AI 초안 생성'}
              </button>
              <button
                onClick={handleGenerate}
                disabled={isBusy}
                className="text-xs px-3 py-1.5 border border-slate-200 rounded hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                ↻ 재생성
              </button>
              <button
                onClick={handleApprove}
                disabled={isBusy || draft.status === 'draft' || draft.status === 'blocked'}
                className="text-xs px-3 py-1.5 bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:bg-slate-200 disabled:text-slate-400"
              >
                {busy[selectedQid] === 'approving' ? '승인 중...' : '✓ 승인'}
              </button>
              <button className="text-xs px-3 py-1.5 text-slate-500 hover:bg-slate-50 rounded">
                ↶ 되돌리기
              </button>
            </div>
          )}
        </div>

        {/* 우: 탭 패널 (보완자료 | AI 챗봇) — C-5c */}
        <div className="bg-white border border-slate-200 rounded-md flex flex-col overflow-hidden">
          {/* 탭 헤더 */}
          <div className="flex border-b border-slate-200">
            <button
              onClick={() => handleRightTabChange('supplemental')}
              className={`flex-1 px-3 py-2.5 text-sm font-medium transition ${
                rightTab === 'supplemental'
                  ? 'text-indigo-950 border-b-2 border-indigo-950 -mb-px'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              보완자료
              {currentMissingCount > 0 && (
                <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 font-semibold">
                  {currentMissingCount}
                </span>
              )}
            </button>
            <button
              onClick={() => handleRightTabChange('chat')}
              className={`flex-1 px-3 py-2.5 text-sm font-medium transition ${
                rightTab === 'chat'
                  ? 'text-indigo-950 border-b-2 border-indigo-950 -mb-px'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              AI 챗봇
            </button>
          </div>

          {/* 탭 본문 */}
          {rightTab === 'supplemental' ? (
            <div className="flex-1 overflow-hidden">
              <SupplementalPanel
                sessionId={sessionId}
                selectedQid={selectedQid}
                formData={formData}
                missingMaterials={localMissingMaterials}
                onMissingChange={() => {}}
                onSupplementalChange={wrappedSupplementalChange}
                supplementalMaterials={supplementalMaterials}
              />
            </div>
          ) : (
            <>
              <div className="px-4 py-3 border-b border-slate-200">
                <span className="font-semibold text-slate-900">AI 보완 (draft_rewriter)</span>
                <div className="text-[10px] text-slate-400 mt-0.5">현재 문항 컨텍스트 자동 유지</div>
              </div>

              <div className="flex-1 overflow-y-auto p-3 space-y-2">
                {chat.map((m, i) => (
                  <div
                    key={i}
                    className={`text-sm rounded p-2.5 ${
                      m.role === 'ai'
                        ? 'bg-slate-50 text-slate-800'
                        : 'bg-indigo-50 text-indigo-900 ml-8'
                    }`}
                  >
                    <div className="text-[10px] uppercase tracking-wider font-semibold mb-1 opacity-70">
                      {m.role === 'ai' ? 'AI' : '사용자'}
                    </div>
                    <div className="leading-relaxed whitespace-pre-wrap">{m.text}</div>
                    {m.role === 'ai' && (m.text.includes('수정 제안') || m.text.includes('제안')) && (
                      <div className="mt-2 flex gap-1.5">
                        <button
                          onClick={() => handleApplyRewrite(m.text)}
                          disabled={isBusy}
                          className="text-[11px] px-2 py-1 bg-indigo-950 text-white rounded hover:bg-indigo-900 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {busy[selectedQid] === 'rewriting' ? '적용 중...' : '적용'}
                        </button>
                        <button className="text-[11px] px-2 py-1 border border-slate-200 rounded">거부</button>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <div className="p-2 border-t border-slate-200">
                <div className="flex gap-1.5">
                  <input
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && !busy._chat && handleSendChat()}
                    disabled={busy._chat}
                    placeholder={busy._chat ? 'AI 응답 생성 중...' : '이 부분 더 강조해줘 / 짧게 / 정량적으로...'}
                    className="flex-1 text-sm px-2 py-1.5 border border-slate-200 rounded disabled:bg-slate-50"
                  />
                  <button
                    onClick={handleSendChat}
                    disabled={busy._chat}
                    className="text-xs px-3 py-1.5 bg-indigo-950 text-white rounded hover:bg-indigo-900 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {busy._chat ? '...' : '전송'}
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* 네비게이션 바 (좌끝 이전 / 우끝 다음) */}
      <StepNavigationBar
        onPrev={onPrev}
        onNext={onNext}
        prevLabel="← 이전 (Step 2)"
        nextLabel="다음 → (Step 4)"
      />
    </div>
  )
}
