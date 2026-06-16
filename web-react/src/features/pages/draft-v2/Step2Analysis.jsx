// AJIN BizAI v0.2 — Step 2: 분석 (사용자 모드)
// 출처: PRD §4~§6 / §19.2 / mockup_final.html (709~1256)
// 포함: Tab 1 공고문 분석 + Tab 2 제출양식 분석 (좌트리/중PDF/우보완)
//
// Phase 4-G-2: Tab 1 parse-notice API 연결
//   - sessionId + notice props 받아서 POST /api/analysis/parse-notice 호출
//   - 응답을 NOTICE_MOCK shape으로 adapter 변환 후 Tab1NoticeAnalysis에 prop 전달
//   - sessionId 없으면 mock 그대로 fallback (오프라인 동작 보존)

import { useState, useEffect, useMemo, useCallback } from 'react'
import { Pencil } from 'lucide-react'
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels'
import { analysisApi } from '../../../api/backendApi'
import { logApi, handleFallback } from '../../../lib/runtimeLog'
import FormTreePanel, { FORM_MOCK } from './shared/FormTreePanel'

// form_prd/2.md: MOCK 자동 사용 금지 — DB·캐시 둘 다 없을 때 빈 상태로 표시
const EMPTY_FORM = {
  stats: { total: 0, sections: 0, tables: 0 },
  sections: [],
  excluded_question_ids: [],
  user_question_metadata: {},
}

// 동일 정책: notice도 MOCK 자동 사용 금지
const EMPTY_NOTICE = {
  fact: [],
  evaluation_criteria: [],
}
import FormPreviewPanel from './shared/FormPreviewPanel'
import SupplementalPanel from './shared/SupplementalPanel'
import FormQuestionEditor from './shared/FormQuestionEditor'
import Step2SummaryPanel from './components/Step2SummaryPanel'
import StepNavigationBar from './components/StepNavigationBar'
// v0.2.1 V3: 평가기준 매핑 편집
import EvalCriteriaMappingEditModal from './shared/EvalCriteriaMappingEditModal'
import {
  generateCriteriaId,
  mergeEvalCriteriaMappings as mergeMappingItems,  // adapter (base+overlay item merge)
} from '../../../lib/evalCriteriaMappingAdapter'
// v0.2.1 QG-1: Step 2 Footer Quality Diagnostic
import {
  computeStep2QualityMetrics,
  detectStep2RiskSignals,
  getRiskBadgeMeta,
} from '../../../lib/step2QualityDiagnostic'

// ─── Mock Data (PRD §13.2 NoticeSchema 기반, fallback용 — sessionId 없거나 API 실패 시 사용) ───
const NOTICE_MOCK = {
  fact: [
    { key: '사업명', value: '2026년 중소기업 디지털 전환 지원사업', source: 'p.1', strong: true },
    { key: '주관기관', value: '중소벤처기업부 · 한국산업기술진흥원', source: 'p.1' },
    { key: '지원 목적', value: '중소·중견기업의 AI·데이터 기반 공정 고도화 지원', source: 'p.2' },
    { key: '지원 대상', value: '제조업 중소기업 (업력 3년 이상, 상시근로자 10인 이상)', source: 'p.3' },
    { key: '지원 규모', value: '총 사업비의 70% 이내, 최대 2억 원 · 1차연도 1억 / 2차연도 1억', source: 'p.4' },
    { key: '필수 제출서류', value: '사업계획서 · 사업자등록증 · 재무제표(직전 2개년) · 4대보험가입자명부', source: 'p.10' },
    { key: '마감일', value: '2026-06-15 18:00 · 온라인 접수', source: 'p.11', error: true },
    { key: '제한사항', value: '최근 3년 내 동일 사업 수혜 기업 제외', source: 'p.12' },
  ],
  evaluation_criteria: [
    {
      name: '기술성', score: 40,
      mappings: [
        { qid: 'III-1', scope: 'question', conf: 0.92 },
        { qid: 'III-T1', scope: 'question', conf: 0.85 },
      ],
    },
    {
      name: '사업성', score: 30,
      mappings: [
        { qid: 'II-1', scope: 'section', conf: 0.78 },
        { qid: 'III-2', scope: 'section', conf: 0.81 },
        { qid: 'V-1', scope: 'section', conf: 0.74 },
      ],
    },
    {
      name: '수행역량', score: 30,
      mappings: [
        { qid: 'I-3', scope: 'question', conf: 0.88 },
        { qid: 'IV-2', scope: 'document', conf: 0.62 },
      ],
    },
  ],
  evaluation_source: 'p.8',
  ai_interpretation: {
    '핵심 평가 포인트': [
      'AI/데이터 기술의 **실 적용 가능성**이 기술성 점수의 핵심',
      '매출 증대·비용 절감 등 **정량적 사업성** 강조 필요',
      '유사 프로젝트 수행 실적이 수행역량 평가에 직결',
    ],
    '작성 시 강조할 내용': [
      'AS-IS / TO-BE 공정 비교를 정량 지표로 제시',
      '1·2차연도 단계별 성과지표(KPI) 명확화',
      '사업 종료 후 자립 운영 계획 포함',
    ],
    '주의해야 할 리스크': [
      '"디지털 전환"의 추상적 서술은 감점 요인',
      '총사업비 산출 근거가 약하면 사업성 점수 하락',
      '3년 내 유사 사업 수혜 이력 사전 확인 필수',
    ],
    '부족자료 예상': [
      '시장 규모·고객 수요 입증 외부 근거',
      '경쟁사 대비 기술 차별성 비교 자료',
    ],
  },
  prompt_version: 'notice_analyst_v001',
}

// ─── Helper: bold 마크다운 (**text**) → <strong> ───
function renderBold(text) {
  return text.split(/(\*\*[^*]+\*\*)/).map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>
    }
    return <span key={i}>{part}</span>
  })
}

// ─── NoticeExtraFact.value 안전 렌더 (text / list / table / amount / boolean / object) ───
function formatExtraValue(v, valueType) {
  if (v == null) return ''
  if (typeof v === 'string') return v
  if (typeof v === 'boolean') return v ? '예' : '아니오'
  if (typeof v === 'number') return String(v)
  if (Array.isArray(v)) {
    return v.map(item => {
      if (item == null) return ''
      if (typeof item === 'string' || typeof item === 'number') return String(item)
      if (typeof item === 'object') {
        // table row 또는 object: key: value 쌍을 / 로 묶음
        return Object.entries(item).map(([k, vv]) => `${k}: ${vv}`).join(' / ')
      }
      return String(item)
    }).join(valueType === 'table' ? ' | ' : ', ')
  }
  if (typeof v === 'object') {
    return Object.entries(v).map(([k, vv]) => `${k}: ${vv}`).join(' / ')
  }
  return String(v)
}

// ─── Backend NoticeSchema → 기존 NOTICE_MOCK shape adapter ───
function adaptNoticeFromApi(apiResp) {
  // MOCK 자동 사용 금지 — 빈 응답이면 EMPTY 반환
  if (!apiResp) return EMPTY_NOTICE
  const sp = apiResp.source_pages || {}
  const fact = []
  if (apiResp.target) fact.push({ key: '지원 대상', value: apiResp.target, source: sp.target ? `p.${sp.target}` : '' })
  if (apiResp.benefit) fact.push({ key: '지원 규모', value: apiResp.benefit, source: sp.benefit ? `p.${sp.benefit}` : '', strong: true })
  if (apiResp.total_budget) fact.push({ key: '총 예산', value: apiResp.total_budget, source: sp.total_budget ? `p.${sp.total_budget}` : '' })
  if (apiResp.application_period_start || apiResp.deadline) {
    const period = apiResp.application_period_start && apiResp.deadline
      ? `${apiResp.application_period_start} ~ ${apiResp.deadline}`
      : (apiResp.deadline || apiResp.application_period_start)
    fact.push({ key: '신청 기간', value: period, source: sp.deadline ? `p.${sp.deadline}` : '', error: true })
  }
  if (apiResp.submission_system) fact.push({ key: '신청 시스템', value: apiResp.submission_system, source: '' })
  if (apiResp.required_documents?.length) {
    fact.push({ key: '필수 제출서류', value: apiResp.required_documents.join(' · '), source: sp.required_documents ? `p.${sp.required_documents}` : '' })
  }
  if (apiResp.process_steps?.length) {
    fact.push({ key: '평가 절차', value: apiResp.process_steps.join(' → '), source: '' })
  }
  if (apiResp.exclusion_conditions?.length) {
    fact.push({ key: '제한사항', value: apiResp.exclusion_conditions.join(' · '), source: '' })
  }
  if (apiResp.important_keywords?.length) {
    fact.push({ key: '핵심 키워드', value: apiResp.important_keywords.join(', '), source: '' })
  }
  // extras (반정형) — category별 그룹핑해서 fact 하단에 추가
  if (Array.isArray(apiResp.extras) && apiResp.extras.length) {
    const byCategory = {}
    for (const x of apiResp.extras) {
      if (!x || x.value == null || x.value === '') continue
      const cat = x.category || '기타'
      if (!byCategory[cat]) byCategory[cat] = []
      byCategory[cat].push(x)
    }
    // importance high 우선, 다음 medium, low 순서로 카테고리 정렬
    const importanceWeight = { high: 3, medium: 2, low: 1 }
    const sortedCats = Object.keys(byCategory).sort((a, b) => {
      const wa = Math.max(...byCategory[a].map(it => importanceWeight[it.importance] || 1))
      const wb = Math.max(...byCategory[b].map(it => importanceWeight[it.importance] || 1))
      return wb - wa
    })
    for (const cat of sortedCats) {
      const items = byCategory[cat]
      const value = items.map(it => {
        const v = formatExtraValue(it.value, it.value_type)
        return it.label ? `${it.label}: ${v}` : v
      }).join(' · ')
      const pages = [...new Set(items.map(it => it.source_page).filter(Boolean))]
      fact.push({
        key: cat,
        value,
        source: pages.length ? `p.${pages.join(',')}` : '',
        extras_meta: items,  // 디버그 모드용 원본 보존
      })
    }
  }

  // evaluation_criteria: backend weight → frontend score, mappings는 form_parser 이후에 채워짐 → 빈 배열
  // v1.7 (2026-05-18): stage / stage_total / stage_order / criterion_type / sub_criteria 통과
  const evaluation_criteria = (apiResp.evaluation_criteria || []).map(c => ({
    name: c.name,
    score: c.weight ?? c.score ?? 0,
    scope: c.scope,
    stage: c.stage ?? null,
    stage_total: c.stage_total ?? null,
    stage_order: c.stage_order ?? null,
    criterion_type: c.criterion_type ?? 'score',
    sub_criteria: Array.isArray(c.sub_criteria) ? c.sub_criteria : [],
    mappings: c.mapped_questions || [],
  }))

  return {
    fact,
    evaluation_criteria,
    evaluation_source: sp.evaluation_criteria ? `p.${sp.evaluation_criteria}` : '-',
    ai_interpretation: apiResp.ai_interpretation || {},
    prompt_version: apiResp._prompt_version || apiResp.prompt_version || 'notice_analyst_v001',
  }
}

// ─── Phase 4-G-4: map-eval-criteria 결과를 noticeData.evaluation_criteria mappings에 머지 ───
// backend 응답: { mappings: [{criteria_name, mapped_questions, mapping_type, confidence, ...}], total }
function mergeEvalCriteriaMappings(noticeData, evalCriteriaMapping) {
  if (!evalCriteriaMapping?.mappings) return noticeData
  const byName = {}
  evalCriteriaMapping.mappings.forEach(c => {
    // mapped_questions가 [{question_id, scope, conf}] 형태일 수도 있고 단순 string 배열일 수도
    byName[c.criteria_name] = (c.mapped_questions || []).map(mq => {
      if (typeof mq === 'string') {
        return { qid: mq, scope: c.scope || 'question', conf: c.confidence || 0.5 }
      }
      return {
        qid: mq.question_id || mq.qid,
        scope: mq.scope || c.scope || 'question',
        conf: mq.confidence || mq.conf || c.confidence || 0.5,
      }
    })
  })
  return {
    ...noticeData,
    evaluation_criteria: noticeData.evaluation_criteria.map(c => ({
      ...c,
      mappings: byName[c.name]?.length ? byName[c.name] : (c.mappings || []),
    })),
  }
}

// ─── Phase 4-G-4: mapping + missing 결과를 question status로 머지 ───
// 2026-05-18: Step3Draft도 사용 — export로 공유
// 2026-05-18: excludedIds 인자 추가 — 사용자 "작성 제외" 표시한 항목은 status='excluded'
export function applyStatusToForm(formData, mappingResult, missingMaterials, excludedIds = null) {
  if (!mappingResult && !missingMaterials) return formData

  const missingByQid = {}
  if (Array.isArray(missingMaterials)) {
    missingMaterials.forEach(m => {
      missingByQid[m.question_id] = m
    })
  }
  const mappingByQid = {}
  if (mappingResult?.question_mappings) {
    mappingResult.question_mappings.forEach(qm => {
      mappingByQid[qm.question_id] = qm
    })
  }

  const excludedSet = new Set(Array.isArray(excludedIds) ? excludedIds : (formData?.excluded_question_ids || []))

  const sections = formData.sections.map(sec => ({
    ...sec,
    questions: sec.questions.map(q => {
      let status = q.status || 'ok'
      const miss = missingByQid[q.id]
      const map = mappingByQid[q.id]
      // 2026-05-18: 제목 항목 (작성 불가) — badge 표시 안 함
      //   조건: header_candidate hint OR (fill_mode=ai_text + max_length=0 + 짧은 title)
      const fillMode = q.fillMode || q.fill_mode
      const maxLen = q.maxLength ?? q.constraints?.max_length ?? null
      const isWritable = (
        fillMode === 'table_input' ||
        (fillMode === 'ai_text' && (maxLen === null || maxLen > 0)) ||
        fillMode === 'file_attach'
      )
      const isHeaderLike = !isWritable && (maxLen === 0 || maxLen === null)
      // 2026-05-18: 사용자 "작성 제외" 표시 우선 (mapping/draft 결과 무시)
      if (excludedSet.has(q.id)) {
        status = 'excluded'
      } else if (isHeaderLike) {
        status = null  // badge 표시 안 함 (제목 항목)
      } else if (map) {
        // 2026-05-18 E-2 vector RAG 통합: match_status + matched_evidence_ids 우선
        const hasEvidence = Array.isArray(map.matched_evidence_ids) && map.matched_evidence_ids.length > 0
        if (map.match_status === 'no_match' || !hasEvidence) {
          status = 'missing'
        } else if (map.match_status === 'auto_confirmed' || map.confidence_score >= 0.75) {
          status = 'ok'
        } else {
          status = 'weak'   // awaiting_user_confirm (0.60~0.75)
        }
      } else if (miss) {
        // mapping 결과에 없지만 missing_material만 있는 경우 (이전 mock 호환)
        status = miss.input_type === 'text' ? 'weak' : 'missing'
      }
      return { ...q, status }
    }),
  }))

  return { ...formData, sections }
}

function deriveStatusStats(formDataWithStatus) {
  if (!formDataWithStatus?.sections) return { ok: 0, weak: 0, missing: 0, excluded: 0, total: 0 }
  let ok = 0, weak = 0, missing = 0, excluded = 0
  formDataWithStatus.sections.forEach(sec => {
    sec.questions.forEach(q => {
      if (q.status === 'excluded') excluded++
      else if (q.status === 'missing') missing++
      else if (q.status === 'weak') weak++
      else ok++
    })
  })
  // total은 excluded 제외 (작성 항목 카운트)
  return { ok, weak, missing, excluded, total: ok + weak + missing }
}

// 2026-05-18: form_parser가 신 스키마 (table_schema.columns) / 구 (table_columns) 둘 다 반환 가능
// 컬럼 개수만 계산해 트리 메타에 표시
function getTableColumnCount(q) {
  const tc = q?.table_columns
  if (Array.isArray(tc) && tc.length) return tc.length
  const sc = q?.table_schema?.columns
  if (Array.isArray(sc) && sc.length) return sc.length
  // 옛 응답: table_columns가 숫자 (e.g., 4)
  if (typeof tc === 'number') return tc
  return 0
}

// ─── Backend FormSchema → 기존 FORM_MOCK shape adapter (Phase 4-G-3) ───
// 2026-05-18: DraftPageV2도 복원 시 사용 — export로 공유
export function adaptFormFromApi(apiResp) {
  // form_prd/2.md: MOCK 자동 사용 금지 — 빈 응답이면 EMPTY 반환
  if (!apiResp || !apiResp.sections) return EMPTY_FORM
  // 2026-05-18: excluded_question_ids 직접 적용 (적어도 트리에서 status badge 변경)
  const excludedSet = new Set(Array.isArray(apiResp.excluded_question_ids) ? apiResp.excluded_question_ids : [])
  let totalQuestions = 0
  let totalTables = 0
  const sections = apiResp.sections.map((sec) => {
    const questions = (sec.questions || []).map((q) => {
      totalQuestions += 1
      if (q.is_table_item) totalTables += 1
      const meta = []
      if (q.is_table_item) {
        const cnt = getTableColumnCount(q)
        meta.push(cnt > 0 ? `표 (${cnt}열)` : '표')
      } else if (q.constraints?.max_length) meta.push(`${q.constraints.max_length.toLocaleString()}자`)
      if (q.is_required) meta.push('필수')
      if (q.source_page) meta.push(`p.${q.source_page}`)
      // 2026-05-18 C-단계: parser hint 표시 (자동 변환 X, 사용자 결정)
      const hint = q._parser_hint
      if (hint?.table_candidate) meta.push('💡 표 가능성')
      else if (hint?.header_candidate) meta.push('💡 제목 가능성')
      else if (hint?.blank_marker) meta.push('💡 작성요청 빈칸')
      // 2026-05-18: 진짜 제목 항목만 badge 생략 (header_candidate hint 기반 — 더 엄격)
      //   form_parser가 max_length=0 기본값으로 주는 경우 다수 → maxlen만으로 header 판단 X
      //   header_candidate hint는 postprocessor가 (짧은 title + 본문 없음 + maxLen=0) 조건으로 부여
      const isHeaderLike = !!(hint?.header_candidate)
      // 2026-05-18: excluded 우선 → header → ok
      let status = 'ok'
      if (excludedSet.has(q.question_id)) status = 'excluded'
      else if (isHeaderLike) status = null  // badge 표시 안 함 (진짜 제목)
      return {
        id: q.question_id,
        title: q.title,
        status,
        meta,
        // 트리 클릭 시 PDF 페이지 점프용 numeric 값 보존
        source_page: typeof q.source_page === 'number' ? q.source_page : null,
      }
    })
    return {
      id: sec.section_id,
      title: sec.title,
      count: `${questions.length} 문항`,
      questions,
    }
  })
  return {
    stats: {
      total: totalQuestions,
      sections: sections.length,
      tables: totalTables,
    },
    sections,
    // form_prd/4.md + 5.md: 메타 보존 — FormTreePanel이 트리 필터링에 사용
    excluded_question_ids: Array.isArray(apiResp.excluded_question_ids) ? apiResp.excluded_question_ids : [],
    user_question_metadata: (apiResp.user_question_metadata && typeof apiResp.user_question_metadata === 'object')
      ? apiResp.user_question_metadata
      : {},
  }
}

// ─── selectedNotice / uploads에서 notice_text 추출 ───
function extractNoticeText(notice, uploads) {
  // 업로드된 PDF가 있으면 빈 문자열 반환 → backend가 session.attachments의 parsed_text 사용 (E1)
  if (uploads?.noticeFiles?.length) return ''

  // PDF 없을 때만 notice 메타로 fallback (검색 결과에서 진입한 경우 등)
  const parts = []
  if (notice?.title) parts.push(`공고명: ${notice.title}`)
  if (notice?.org) parts.push(`주관기관: ${notice.org}`)
  if (notice?.target) parts.push(`지원대상: ${notice.target}`)
  if (notice?.benefit) parts.push(`지원내용: ${notice.benefit}`)
  if (notice?.summary) parts.push(`요약: ${notice.summary}`)
  if (notice?.benefit_amount_min) parts.push(`지원금: ${notice.benefit_amount_min}`)
  return parts.join('\n')
}

// ─── Tab 1: 공고문 분석 (mockup 709~844) ───
function Tab1NoticeAnalysis({
  noticeData = NOTICE_MOCK,
  loading = false,
  error = null,
  onEditCriteria = null,   // v0.2.1 V3: 카드별 [✎] 핸들러
  userEditedNames = null,  // Set<string> — mapped_by="user" 인 criteria_name set
  onReanalyze = null,      // 공고문 다시 분석 버튼
  onConfirm = null,        // 공고문 분석 확정 버튼
}) {
  const onJump = (qid) => {
    // TODO Phase 4: Tab 2로 이동 + 해당 question_id 하이라이트
    console.log('jump to question:', qid)
  }

  if (loading) {
    return (
      <div className="bg-white border border-slate-200 rounded-md p-8 text-center text-slate-500">
        <div className="text-sm">공고문 분석 중...</div>
        <div className="text-[11px] mt-1 text-slate-400">notice_analyst 호출</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-amber-50 border border-amber-200 rounded-md p-4 mb-3 text-sm text-amber-900">
        <div className="font-semibold mb-1">⚠ 공고문 분석 실패 — mock 데이터로 표시</div>
        <div className="text-xs">{error}</div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-4">
      {/* 좌측: 원문 추출 정보 (FACT) */}
      <div className="bg-white border border-slate-200 rounded-md">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-900">원문 추출 정보</span>
            <span className="text-[10px] font-medium px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded">FACT</span>
          </div>
          <span className="text-xs px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded">분석 완료</span>
        </div>
        <div className="p-4">
          <div className="space-y-2.5">
            {noticeData.fact.map((row) => (
              <div key={row.key} className="grid grid-cols-[110px_1fr] gap-3 text-sm">
                <div className="text-slate-500 text-xs pt-0.5">{row.key}</div>
                <div className="text-slate-900">
                  {row.error ? (
                    <strong className="text-red-700">{row.value}</strong>
                  ) : row.strong ? (
                    <strong>{row.value}</strong>
                  ) : (
                    row.value
                  )}
                  <span className="ml-2 font-mono text-[11px] text-slate-400">{row.source}</span>
                </div>
              </div>
            ))}

            {/* 평가 기준 grid */}
            <div className="grid grid-cols-[110px_1fr] gap-3 text-sm pt-2">
              <div className="text-slate-500 text-xs pt-0.5">평가 기준</div>
              <div>
                {onEditCriteria && (
                  <div className="text-[10px] text-slate-500 mb-1.5 leading-relaxed">
                    AI가 자동 생성한 평가기준 → 문항 매핑을 검토하고 수정합니다.
                    저장된 매핑은 이후 Step 4 재계산의 기준이 됩니다.
                    이미 작성된 초안 본문은 자동으로 변경되지 않습니다.
                  </div>
                )}
                {(() => {
                  const items = noticeData.evaluation_criteria || []
                  const renderCard = (c) => {
                    const isUserEdited = userEditedNames?.has(c.name)
                    return (
                      <div
                        key={c.name}
                        className={`relative border rounded p-2 ${
                          isUserEdited
                            ? 'border-blue-300 bg-blue-50/40 ring-1 ring-blue-200/60'
                            : 'border-slate-200'
                        }`}
                      >
                        {onEditCriteria && (
                          <button
                            type="button"
                            onClick={() => onEditCriteria(c)}
                            className="absolute top-1.5 right-1.5 w-6 h-6 rounded flex items-center justify-center text-slate-400 hover:text-indigo-700 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 transition-colors"
                            title="평가기준 매핑 편집"
                          >
                            <Pencil className="w-3 h-3" />
                          </button>
                        )}
                        <div className="text-xs text-slate-500 pr-7">{c.name}</div>
                        <div className="text-lg font-semibold text-slate-900">
                          {c.score}<span className="text-xs text-slate-400 ml-0.5">점</span>
                        </div>
                        {/* v1.7: sub_criteria preview (있을 때만, 최대 2개 + 외 N개) */}
                        {Array.isArray(c.sub_criteria) && c.sub_criteria.length > 0 && (
                          <ul className="mt-1 text-[10px] text-slate-500 space-y-0.5">
                            {c.sub_criteria.slice(0, 2).map((s, i) => (
                              <li key={i} className="flex gap-1">
                                <span className="flex-1 truncate" title={s.text}>· {s.text}</span>
                                <span className="text-slate-400 shrink-0">{s.weight}</span>
                              </li>
                            ))}
                            {c.sub_criteria.length > 2 && (
                              <li className="text-slate-400">… 외 {c.sub_criteria.length - 2}개</li>
                            )}
                          </ul>
                        )}
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {c.mappings.map((m) => (
                            <button
                              key={m.qid}
                              onClick={() => onJump(m.qid)}
                              className="text-[10px] px-1.5 py-0.5 bg-indigo-50 text-indigo-900 rounded border border-indigo-100 hover:bg-indigo-100 transition"
                              title={`${m.scope} · ${m.conf}`}
                            >
                              {m.qid}
                              <span className="ml-1 text-indigo-400">{m.scope.slice(0, 1)}·{m.conf}</span>
                            </button>
                          ))}
                          {c.mappings.length === 0 && (
                            <span className="text-[10px] text-slate-400">(매핑 없음)</span>
                          )}
                        </div>
                        {isUserEdited && (
                          <div className="mt-1.5">
                            <span className="inline-block text-[9px] font-semibold px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-200">
                              ✎ 사용자 편집됨
                            </span>
                          </div>
                        )}
                      </div>
                    )
                  }

                  // v1.7: stage 있으면 단계별 그룹핑 (stage_order 우선, 없으면 첫 등장 순)
                  const hasStage = items.some(c => c.stage)
                  if (!hasStage) {
                    return <div className="grid grid-cols-3 gap-2">{items.map(renderCard)}</div>
                  }

                  const groupMap = new Map()
                  items.forEach((c, idx) => {
                    const key = c.stage || '기타'
                    if (!groupMap.has(key)) {
                      groupMap.set(key, {
                        order: c.stage_order ?? (idx + 1000),  // explicit order 우선
                        total: c.stage_total ?? null,
                        items: [],
                      })
                    }
                    groupMap.get(key).items.push(c)
                  })
                  const sortedGroups = [...groupMap.entries()].sort(
                    ([, a], [, b]) => a.order - b.order
                  )
                  return (
                    <div className="space-y-3">
                      {sortedGroups.map(([stageName, g]) => (
                        <div key={stageName}>
                          <div className="text-[11px] font-medium text-slate-600 mb-1.5">
                            {stageName}
                            {g.total != null && (
                              <span className="ml-1 text-slate-400">· {g.total}점</span>
                            )}
                          </div>
                          <div className="grid grid-cols-3 gap-2">{g.items.map(renderCard)}</div>
                        </div>
                      ))}
                    </div>
                  )
                })()}
                <div className="text-[11px] text-slate-400 mt-2 leading-relaxed">
                  주요 반영 위치 후보 · 평가기준은 단일 문항이 아닌 여러 문항·문서 맥락에서 종합 검토됩니다
                  <span className="font-mono ml-1">근거 {noticeData.evaluation_source}</span>
                </div>
                <div className="text-[10px] text-slate-400 mt-1">
                  scope: 적용 범위 (question / section / document) · 0.XX: AI 매핑 신뢰도
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 우측: AI 구조화 해석 */}
      <div className="bg-white border border-slate-200 rounded-md flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-900">AI 구조화 해석</span>
            <span className="text-[10px] font-medium px-1.5 py-0.5 bg-indigo-50 text-indigo-900 rounded">AI</span>
          </div>
          <span className="text-xs px-2 py-0.5 bg-blue-50 text-blue-700 rounded font-mono">
            {noticeData.prompt_version}
          </span>
        </div>
        <div className="p-4 flex-1 space-y-4">
          {Object.entries(noticeData.ai_interpretation || {}).map(([label, items]) => (
            <div key={label}>
              <div className="text-xs font-semibold text-slate-700 mb-1.5">{label}</div>
              <ul className={`space-y-1 text-sm ${label === '주의해야 할 리스크' ? 'text-red-700' : 'text-slate-700'}`}>
                {items.map((item, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-slate-300">·</span>
                    <span>{renderBold(item)}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="flex gap-2 px-4 py-3 border-t border-slate-200">
          <button
            type="button"
            onClick={onReanalyze || undefined}
            disabled={!onReanalyze || loading}
            className="text-sm px-3 py-1.5 border border-slate-200 rounded hover:bg-slate-50 transition disabled:opacity-40 disabled:cursor-not-allowed"
            title={onReanalyze ? '공고문 분석을 다시 실행합니다' : '재분석 불가'}
          >
            ↻ 공고문 다시 분석
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Tab 2: 제출양식 분석 (mockup 845~1256) — 좌/중/우 3분할 ───
function Tab2FormPreview({
  formData = FORM_MOCK,
  formApiResp = null,       // 2026-05-19 Option C: raw backend response (table_schema 포함)
  loading = false,
  error = null,
  sessionId,
  formFileId = null,        // backend attachment file_id (PDF raw)
  formFileName = '',        // 표시용 파일명
  missingMaterials,
  mappingResult,
  onMissingChange,
  onSupplementalChange,
  supplementalMaterials = [],
  hasResult = false,        // formApiResp 존재 여부 — 빈 상태 vs 결과 상태 결정
  onStart = null,           // "📄 제출양식 분석 시작" 버튼
  onReanalyze = null,       // "↻ 양식 다시 분석"
  onConfirm = null,         // "✓ 양식 분석 확정"
  canStart = false,         // 시작 가능 조건 (noticeApiResp 있고 sessionId 있을 때만)
  // form_prd/4.md + 5.md: 문항 수정/추가/제외 핸들러
  onEditQuestion = null,
  onAddInSection = null,
  onToggleExclude = null,
  // 2026-05-18: parser_mode (single/hybrid) selector
  parserMode = 'hybrid',
  onParserModeChange = null,
  // 2026-05-18: Tree CRUD 신규 핸들러
  onAddSection = null,
  onRenameSection = null,
  onDeleteSection = null,
  onReorderSection = null,
  onAddAboveQuestion = null,
  onAddBelowQuestion = null,
  onDeleteQuestion = null,
  onMoveQuestion = null,
}) {
  // 첫 문항을 기본 선택으로
  const firstQid = useMemo(() => {
    for (const sec of formData?.sections || []) {
      const q = (sec.questions || [])[0]
      if (q?.id || q?.question_id) return q.id || q.question_id
    }
    return null
  }, [formData])

  const [selectedQid, setSelectedQid] = useState(firstQid || 'I-1')
  const [currentPage, setCurrentPage] = useState(1)

  // selectedQid → source_page 매핑 + 표시명 lookup
  const selectedQuestion = useMemo(() => {
    for (const sec of formData?.sections || []) {
      for (const q of sec.questions || []) {
        if ((q.id || q.question_id) === selectedQid) return q
      }
    }
    return null
  }, [formData, selectedQid])

  const currentQuestion = selectedQuestion
    ? `${selectedQid} ${selectedQuestion.title || ''}`.trim()
    : selectedQid

  // firstQid 결정되면 selectedQid 초기화 (form 분석 완료 후)
  useEffect(() => {
    if (firstQid && (!selectedQid || selectedQid === 'I-1')) {
      setSelectedQid(firstQid)
    }
  }, [firstQid])  // eslint-disable-line react-hooks/exhaustive-deps

  // selectedQuestion이 source_page 가지면 currentPage 자동 점프
  useEffect(() => {
    const sp = selectedQuestion?.source_page
    if (sp && typeof sp === 'number' && sp >= 1) {
      setCurrentPage(sp)
    }
  }, [selectedQuestion])

  const handleSelect = (qid) => {
    setSelectedQid(qid)
  }

  if (loading) {
    return (
      <div className="bg-white border border-slate-200 rounded-md p-8 text-center text-slate-500">
        <div className="text-sm">제출양식 분석 중...</div>
        <div className="text-[11px] mt-1 text-slate-400">form_parser + evidence_extractor + company_analyzer 병렬 호출</div>
      </div>
    )
  }

  // 빈 상태 — 아직 분석 시작 안 한 경우
  if (!hasResult) {
    return (
      <div className="bg-white border border-slate-200 rounded-md p-10">
        <div className="text-center">
          <div className="text-2xl mb-3">📄</div>
          <div className="text-base font-semibold text-slate-900 mb-2">제출양식 분석 준비</div>
          <div className="text-sm text-slate-600 mb-1">
            공고문 분석 결과를 기반으로 제출양식을 구조화하고 회사 정보를 매칭합니다.
          </div>
        </div>

        {/* 2026-05-18: parser_mode selector */}
        {onParserModeChange && (
          <div className="max-w-md mx-auto mt-6 mb-4">
            <div className="text-xs font-medium text-slate-700 mb-2">분석 모드 선택</div>
            <div className="space-y-2">
              <label className="flex items-start gap-2 p-3 border rounded cursor-pointer hover:bg-slate-50 transition border-slate-200 has-[:checked]:border-indigo-500 has-[:checked]:bg-indigo-50/50">
                <input
                  type="radio"
                  name="parser-mode"
                  value="hybrid"
                  checked={parserMode === 'hybrid'}
                  onChange={() => onParserModeChange('hybrid')}
                  className="mt-1"
                />
                <div className="flex-1 text-left">
                  <div className="text-sm font-medium text-slate-900">🎯 정밀 분석 (Hybrid, 권장)</div>
                  <div className="text-[11px] text-slate-600 mt-0.5">
                    Regex로 chapter 분리 → 각 chapter별 LLM 병렬 호출.
                    section 일관성 ↑, 누락 거의 없음. 약 100~150초, 비용 ~30원.
                  </div>
                </div>
              </label>
              <label className="flex items-start gap-2 p-3 border rounded cursor-pointer hover:bg-slate-50 transition border-slate-200 has-[:checked]:border-indigo-500 has-[:checked]:bg-indigo-50/50">
                <input
                  type="radio"
                  name="parser-mode"
                  value="single"
                  checked={parserMode === 'single'}
                  onChange={() => onParserModeChange('single')}
                  className="mt-1"
                />
                <div className="flex-1 text-left">
                  <div className="text-sm font-medium text-slate-900">⚡ 빠른 분석 (Single)</div>
                  <div className="text-[11px] text-slate-600 mt-0.5">
                    단일 LLM 호출 (전체 한 번에). 짧은 form 적합. 38p+ 긴 form은 section 누락 가능.
                    약 60~120초, 비용 ~3원.
                  </div>
                </div>
              </label>
            </div>
          </div>
        )}

        <div className="text-center mt-4">
          <button
            type="button"
            onClick={onStart ? () => onStart() : undefined}
            disabled={!onStart || !canStart}
            className="text-sm px-4 py-2 bg-indigo-950 text-white rounded hover:bg-indigo-900 transition disabled:opacity-40 disabled:cursor-not-allowed"
            title={canStart ? '제출양식 분석을 시작합니다' : '공고문 분석을 먼저 완료하세요'}
          >
            📄 제출양식 분석 시작
          </button>
          {!canStart && (
            <div className="text-[11px] text-amber-700 mt-3">
              공고문 분석이 완료되어야 시작할 수 있습니다.
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <>
      {error && (
        <div className="mb-3 bg-amber-50 border border-amber-200 rounded-md p-3 text-sm text-amber-900">
          ⚠ 양식 분석 실패 — mock 데이터로 표시: {error}
        </div>
      )}
      {/* 좌/중/우 3 패널 — 드래그 리사이저블 (react-resizable-panels)
          autoSaveId: 사용자가 조절한 폭을 localStorage에 자동 저장 (새로고침 후 유지)
          minSize / maxSize: % 단위 (좌 18-50, 중 30+, 우 18-45) */}
      <div className="h-[calc(100vh-280px)] min-h-[500px]">
        <PanelGroup direction="horizontal" autoSaveId="step2-form-layout" className="h-full">
          <Panel defaultSize={22} minSize={18} maxSize={50} className="overflow-hidden">
            <FormTreePanel
              selectedQid={selectedQid}
              onSelect={handleSelect}
              formData={formData}
              onEditQuestion={onEditQuestion}
              onAddInSection={onAddInSection}
              onToggleExclude={onToggleExclude}
              onAddSection={onAddSection}
              onRenameSection={onRenameSection}
              onDeleteSection={onDeleteSection}
              onReorderSection={onReorderSection}
              onAddAboveQuestion={onAddAboveQuestion}
              onAddBelowQuestion={onAddBelowQuestion}
              onDeleteQuestion={onDeleteQuestion}
              onMoveQuestion={onMoveQuestion}
            />
          </Panel>
          <PanelResizeHandle className="w-1.5 mx-1 bg-slate-100 hover:bg-indigo-300 active:bg-indigo-400 transition-colors cursor-col-resize rounded-full" />
          <Panel minSize={30} className="overflow-hidden">
            <FormPreviewPanel
              sessionId={sessionId}
              formFileId={formFileId}
              formFileName={formFileName}
              currentPage={currentPage}
              currentQuestion={currentQuestion}
              onPageChange={setCurrentPage}
            />
          </Panel>
          <PanelResizeHandle className="w-1.5 mx-1 bg-slate-100 hover:bg-indigo-300 active:bg-indigo-400 transition-colors cursor-col-resize rounded-full" />
          <Panel defaultSize={28} minSize={18} maxSize={45} className="overflow-hidden">
            <SupplementalPanel
              devMode={false}
              sessionId={sessionId}
              selectedQid={selectedQid}
              formData={formData}
              formApiResp={formApiResp}
              missingMaterials={missingMaterials}
              mappingResult={mappingResult}
              onMissingChange={onMissingChange}
              onSupplementalChange={onSupplementalChange}
              supplementalMaterials={supplementalMaterials}
            />
          </Panel>
        </PanelGroup>
      </div>
      {/* Tab1과 일관성 — 양식 결과 하단에 [↻ 다시 분석] / [✓ 양식 분석 확정] */}
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={onReanalyze || undefined}
          disabled={!onReanalyze || loading}
          className="text-sm px-3 py-1.5 border border-slate-200 rounded hover:bg-slate-50 transition disabled:opacity-40 disabled:cursor-not-allowed"
        >
          ↻ 양식 다시 분석
        </button>
        <button
          type="button"
          onClick={onConfirm || undefined}
          disabled={!onConfirm}
          className="text-sm px-3 py-1.5 bg-indigo-950 text-white rounded hover:bg-indigo-900 transition disabled:opacity-40 disabled:cursor-not-allowed"
        >
          ✓ 양식 분석 확정
        </button>
      </div>
    </>
  )
}

// ─── Tab별 footer 요약 데이터 ───

function computeDDay(deadlineStr) {
  if (!deadlineStr) return null
  const d = new Date(deadlineStr)
  if (isNaN(d.getTime())) return null
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  d.setHours(0, 0, 0, 0)
  const days = Math.round((d.getTime() - today.getTime()) / 86_400_000)
  if (days === 0) return { value: 'D-DAY', highlight: 'red' }
  if (days > 0) return { value: `D-${days}`, highlight: days <= 14 ? 'red' : undefined }
  return { value: `D+${Math.abs(days)}`, highlight: 'red' }
}

function shortenCriteriaName(name) {
  const s = String(name || '').trim()
  return s.length > 2 ? s.slice(0, 2) : s || '—'
}

function parseBenefitDisplay(benefit) {
  if (!benefit) return { value: '—' }
  const m = String(benefit).match(/(\d+(?:\.\d+)?)\s*(억|천만|만)\s*원/)
  if (m) return { value: `${m[1]}${m[2]}`, suffix: '원' }
  const trimmed = String(benefit).trim()
  if (!trimmed) return { value: '—' }
  // 숫자 매칭 실패 = 자유 텍스트. isText 플래그로 Summary Panel이 작은 폰트 + 줄바꿈 처리
  return { value: trimmed, isText: true }
}

function buildTab1FooterStats(noticeApiResp) {
  const stats = []

  const dDay = computeDDay(noticeApiResp?.deadline)
  stats.push(dDay ? { label: '마감', ...dDay } : { label: '마감', value: '—' })

  const criteria = noticeApiResp?.evaluation_criteria || []
  if (criteria.length > 0) {
    stats.push({
      label: '평가 기준',
      chips: criteria.map(c => ({ label: shortenCriteriaName(c.name), value: c.weight ?? 0 })),
    })
  } else {
    stats.push({ label: '평가 기준', value: '—' })
  }

  const reqDocsCount = (noticeApiResp?.required_documents || []).length
  stats.push({ label: '필수 서류', value: String(reqDocsCount), suffix: '건' })

  const b = parseBenefitDisplay(noticeApiResp?.benefit)
  stats.push({ label: '지원 한도', ...b })

  return stats
}

const TAB1_FOOTER_HINT = '자료 없음 2 문항은 사용자 직접 작성으로 표시됩니다'

const TAB2_FOOTER_STATS = [
  { label: '추출 문항', value: '18' },
  { label: '작성 가능', value: '14' },
  { label: '근거 부족', value: '3' },
  { label: '자료 없음', value: '1', highlight: 'red' },
]

// Phase 4-G-4: 실시간 question status 통계 → footer
// 분석 전(formDataWithStatus = null)이면 Tab1 footer와 동일하게 '—' 표시
function buildTab2FooterStats(formDataWithStatus) {
  if (!formDataWithStatus) {
    return [
      { label: '추출 문항', value: '—' },
      { label: '작성 가능', value: '—' },
      { label: '근거 부족', value: '—' },
      { label: '자료 없음', value: '—' },
    ]
  }
  const s = deriveStatusStats(formDataWithStatus)
  return [
    { label: '추출 문항', value: String(s.total) },
    { label: '작성 가능', value: String(s.ok) },
    { label: '근거 부족', value: String(s.weak) },
    { label: '자료 없음', value: String(s.missing), highlight: s.missing > 0 ? 'red' : undefined },
  ]
}
const TAB2_FOOTER_HINT = '자료 없음 문항은 사용자 직접 작성으로 표시됩니다'

// ─── v0.2.1 QG-1: 품질 진단 박스 (Footer Quality Diagnostic) ───
// 통과/조건부/검토/실패 자동 판정 X — 수치 + 위험 신호 텍스트만 표시.
const BADGE_COLOR_CLASS = {
  slate:   'bg-slate-100 text-slate-700 border-slate-200',
  amber:   'bg-amber-100 text-amber-800 border-amber-200',
  emerald: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  rose:    'bg-rose-100 text-rose-800 border-rose-200',
}

function Step2QualityDiagnostic({
  noticeApiResp, formData, evalCriteriaMapping,
  mappingResult, missingMaterials, validQuestionIds,
}) {
  const metrics = useMemo(
    () => computeStep2QualityMetrics({
      noticeApiResp, formData, evalCriteriaMapping,
      mappingResult, missingMaterials, validQuestionIds,
    }),
    [noticeApiResp, formData, evalCriteriaMapping, mappingResult, missingMaterials, validQuestionIds]
  )
  const risks = useMemo(() => detectStep2RiskSignals(metrics), [metrics])
  const badge = useMemo(
    () => getRiskBadgeMeta({
      riskCount: risks.count,
      isLoading: metrics.isLoading,
      hasData: metrics.hasData,
    }),
    [risks.count, metrics.isLoading, metrics.hasData]
  )

  const fmt = (v, suffix = '') => v == null ? '—' : `${v}${suffix}`
  const sufficiencyDisplay = metrics.sufficiencyPercent == null
    ? '데이터 없음'
    : `${metrics.sufficiencyPercent}%`

  return (
    <div className="mt-3 bg-white border border-slate-200 rounded-md px-5 py-3.5">
      {/* 헤더: 제목 + badge */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-600">
            품질 진단
          </span>
          <span className="text-[10px] text-slate-400">(참고용 · 자동 판정 X)</span>
        </div>
        <span className={`text-[11px] px-2 py-0.5 rounded-full border font-medium ${BADGE_COLOR_CLASS[badge.color] || BADGE_COLOR_CLASS.slate}`}>
          {badge.label}
        </span>
      </div>

      {/* 3행 수치 grid */}
      <div className="space-y-1 text-xs text-slate-700 font-mono">
        {/* 1행 — form question 분포 */}
        <div>
          추출 문항 <strong>{fmt(metrics.questionCount)}</strong>
          <span className="mx-2 text-slate-300">·</span>
          작성 가능 <strong>{fmt(metrics.okCount)}</strong>
          <span className="mx-2 text-slate-300">·</span>
          근거 부족 <strong>{fmt(metrics.weakCount)}</strong>
          <span className="mx-2 text-slate-300">·</span>
          자료 없음 <strong className={metrics.missingCount > 0 ? 'text-rose-700' : ''}>{fmt(metrics.missingCount)}</strong>
        </div>
        {/* 2행 — sufficiency + eval criteria */}
        <div>
          자료 충족도 <strong>{sufficiencyDisplay}</strong>
          <span className="text-slate-400 ml-1">(참고)</span>
          <span className="mx-2 text-slate-300">·</span>
          평가기준 <strong>{fmt(metrics.evalCriteriaCount, '개')}</strong>
          <span className="mx-2 text-slate-300">·</span>
          배점 합 <strong>{fmt(metrics.evalCriteriaWeightSum)}</strong>
        </div>
        {/* 3행 — 진단 보조 */}
        <div>
          필수서류 <strong>{fmt(metrics.requiredDocsCount, '개')}</strong>
          <span className="mx-2 text-slate-300">·</span>
          source_page 누락 <strong className={metrics.sourcePageMissingCount > 0 ? 'text-amber-700' : ''}>{fmt(metrics.sourcePageMissingCount)}</strong>
          <span className="mx-2 text-slate-300">·</span>
          invalid qid <strong className={metrics.invalidQuestionIdCount > 0 ? 'text-rose-700' : ''}>{fmt(metrics.invalidQuestionIdCount)}</strong>
          {metrics.duplicateQuestionIdCount > 0 && (
            <>
              <span className="mx-2 text-slate-300">·</span>
              dup qid <strong className="text-rose-700">{metrics.duplicateQuestionIdCount}</strong>
            </>
          )}
        </div>
      </div>

      {/* 4행 — 위험 신호 텍스트 (최대 3개 + 외 N개) */}
      {risks.count > 0 && (
        <div className="mt-2 pt-2 border-t border-slate-100 space-y-0.5">
          {risks.displayedSignals.map((sig, i) => (
            <div key={i} className="text-[11px] text-amber-800">
              ⚠ {sig}
            </div>
          ))}
          {risks.hiddenCount > 0 && (
            <div className="text-[11px] text-slate-500">외 {risks.hiddenCount}개</div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Step 2 Analysis (Tab 1 + Tab 2) ───
const STEP2_ACTIVE_TAB_KEY = 'ajin_v2_step2_active_tab'
const STEP2_CACHE_KEY_PREFIX = 'ajin_v2_step2_cache_'  // 뒤에 session_id 결합

function readSavedActiveTab() {
  const v = sessionStorage.getItem(STEP2_ACTIVE_TAB_KEY)
  return v === 'notice' || v === 'form' ? v : 'notice'
}

// Step 2 분석 결과 캐시 — sessionId별 분리.
// 새로고침 시 noticeApiResp / formApiResp 등 복원 → useEffect 자동 재호출 차단.
function readStep2Cache(sessionId) {
  if (!sessionId) return null
  try {
    const raw = sessionStorage.getItem(STEP2_CACHE_KEY_PREFIX + sessionId)
    if (!raw) return null
    return JSON.parse(raw)
  } catch (err) {
    console.warn('[STEP2_CACHE_READ_FAILED]', err)
    return null
  }
}

function writeStep2Cache(sessionId, patch) {
  if (!sessionId) return
  try {
    const prev = readStep2Cache(sessionId) || {}
    const next = { ...prev, ...patch }
    sessionStorage.setItem(STEP2_CACHE_KEY_PREFIX + sessionId, JSON.stringify(next))
  } catch (err) {
    console.warn('[STEP2_CACHE_WRITE_FAILED]', err)
  }
}

export default function Step2Analysis({
  onPrev, onConfirmStep2, onToggleDevMode, sessionId, notice, uploads, onAnalysisReady,
  supplementalMaterials = [],        // post-fix 1: DraftPageV2가 owner
  onSupplementalChangeLifted,        // post-fix 1: 부모 setter
  restoredFormSchema = null,         // form_prd/2.md: DB form_schema_json.schema 복원값
  restoredNoticeSchema = null,       // 동일 패턴: DB notice_schema_json.schema 복원값
  restoreChecked = false,            // form_prd/6.md: getSession 완료 여부 — auto-trigger 게이트
}) {
  const [activeTab, setActiveTab] = useState(() => readSavedActiveTab())

  // activeTab 변경 시 sessionStorage 영속화 (새로고침 시 마지막 탭 복원)
  useEffect(() => {
    sessionStorage.setItem(STEP2_ACTIVE_TAB_KEY, activeTab)
  }, [activeTab])

  // form_prd/2.md: DB schema가 비동기로 도착한 경우 state 동기화
  // 2026-05-18: stale cache 방지 — DB와 cache의 section count + hint 존재 여부 비교
  // C 후처리 hint, table_schema 등 backend가 추가로 주입한 메타가 cache에 없으면 갱신.
  useEffect(() => {
    if (!restoredFormSchema) return
    const dbSecCount = restoredFormSchema.sections?.length || 0
    const curSecCount = formApiResp?.sections?.length || 0
    // hint 존재 여부 비교 (C 단계에서 backend가 _parser_hint 주입)
    const hasHintsDb = (restoredFormSchema.sections || []).some(s =>
      (s.questions || []).some(q => q?._parser_hint || (q?.table_schema?.columns || []).length > 0)
    )
    const hasHintsCache = (formApiResp?.sections || []).some(s =>
      (s.questions || []).some(q => q?._parser_hint || (q?.table_schema?.columns || []).length > 0)
    )
    // sec count 같고 + hint 상태도 같으면 skip
    if (formApiResp && dbSecCount === curSecCount && hasHintsDb === hasHintsCache) return
    setFormApiResp(restoredFormSchema)
    setFormData(adaptFormFromApi(restoredFormSchema))
    setFormFetched(true)
  }, [restoredFormSchema])  // eslint-disable-line react-hooks/exhaustive-deps

  // 동일 패턴: DB notice schema — section 개념 없으니 evaluation_criteria 길이로 비교
  useEffect(() => {
    if (!restoredNoticeSchema) return
    const dbCritCount = restoredNoticeSchema.evaluation_criteria?.length || 0
    const curCritCount = noticeApiResp?.evaluation_criteria?.length || 0
    if (noticeApiResp && dbCritCount === curCritCount) return
    setNoticeApiResp(restoredNoticeSchema)
    setNoticeData(adaptNoticeFromApi(restoredNoticeSchema))
    setNoticeFetched(true)
  }, [restoredNoticeSchema])  // eslint-disable-line react-hooks/exhaustive-deps

  // 분석 결과 캐시 — mount 시 1회 읽음. sessionId 변경 시 새 캐시.
  const initialCache = useMemo(() => readStep2Cache(sessionId), [sessionId])

  // Phase 4-G-2: parse-notice API 통합. 캐시 있으면 그것으로 초기화 → useEffect 재호출 차단.
  // 우선순위 DB(restoredNoticeSchema) > sessionStorage cache > EMPTY_NOTICE (MOCK 자동 사용 금지)
  const [noticeData, setNoticeData] = useState(() => {
    if (restoredNoticeSchema) return adaptNoticeFromApi(restoredNoticeSchema)
    if (initialCache?.noticeData) return initialCache.noticeData
    return EMPTY_NOTICE
  })
  const [noticeLoading, setNoticeLoading] = useState(false)
  const [noticeError, setNoticeError] = useState(null)
  const [noticeFetched, setNoticeFetched] = useState(() =>
    !!restoredNoticeSchema || !!initialCache?.noticeApiResp
  )

  // Phase 4-G-3: parse-form / extract-evidence / analyze-company
  // form_prd/2.md: 우선순위 DB(restoredFormSchema) > sessionStorage cache > EMPTY_FORM
  // MOCK 자동 사용 금지 — 분석 전이면 빈 상태로 표시.
  const [formData, setFormData] = useState(() => {
    if (restoredFormSchema) return adaptFormFromApi(restoredFormSchema)
    if (initialCache?.formData) return initialCache.formData
    return EMPTY_FORM
  })
  const [formApiResp, setFormApiResp] = useState(() =>
    restoredFormSchema || initialCache?.formApiResp || null
  )
  const [noticeApiResp, setNoticeApiResp] = useState(() =>
    restoredNoticeSchema || initialCache?.noticeApiResp || null
  )
  const [formLoading, setFormLoading] = useState(false)
  const [formError, setFormError] = useState(null)
  const [formFetched, setFormFetched] = useState(() =>
    !!restoredFormSchema || !!initialCache?.formApiResp
  )
  const [evidenceData, setEvidenceData] = useState(() => initialCache?.evidenceData || null)
  // eslint-disable-next-line no-unused-vars
  const [companyData, setCompanyData] = useState(() => initialCache?.companyData || null)

  // Phase 4-G-4: mapping / missing / eval-criteria mapping (parse-form 완료 후)
  const [mappingResult, setMappingResult] = useState(null)
  const [missingMaterials, setMissingMaterials] = useState(null)
  // eslint-disable-next-line no-unused-vars
  const [evalCriteriaMapping, setEvalCriteriaMapping] = useState(null)
  const [mappingFetched, setMappingFetched] = useState(false)

  // Phase 4-G-7b post-fix 1: supplementalMaterials owner = DraftPageV2 (lift up)
  // local state 제거 — props로 받고 upsert는 부모 setter 위임

  // v0.2.1 V3: 사용자 편집 mapping (backend GET) + 편집 모달
  const [userMappingItems, setUserMappingItems] = useState([])     // backend GET 결과
  const [editingCriteria, setEditingCriteria] = useState(null)     // 현재 편집 중인 criteria (모달 열린 상태)

  // FormSchema에서 validQuestionIds 추출 (race 처리용)
  const validQuestionIds = useMemo(() => {
    if (!formData?.sections) return []
    const ids = []
    for (const sec of formData.sections) {
      for (const q of (sec.questions || [])) {
        if (q.id) ids.push(q.id)
      }
    }
    return ids
  }, [formData])

  // userEditedNames: mapped_by="user"인 criteria_name set (카드 배지용)
  const userEditedNames = useMemo(() => {
    const s = new Set()
    for (const it of userMappingItems) {
      if (it.mapped_by === 'user' && it.criteria_name) s.add(it.criteria_name)
    }
    return s
  }, [userMappingItems])

  // sessionId 있을 때 GET list 호출 (사용자 편집된 매핑 복원)
  useEffect(() => {
    if (!sessionId) return
    let cancelled = false
    ;(async () => {
      try {
        const res = await analysisApi.listEvalCriteriaMappings(sessionId)
        if (cancelled) return
        setUserMappingItems(res.items || [])
      } catch (err) {
        console.warn('[EVAL_CRITERIA_LIST_FAILED]', err)
      }
    })()
    return () => { cancelled = true }
  }, [sessionId])

  // 편집 핸들러 — c는 noticeData.evaluation_criteria의 row (mergeEvalCriteriaMappings 적용 후)
  const handleEditCriteria = (c) => {
    // backend GET에서 user 편집된 row 우선
    const userRow = userMappingItems.find(u => u.criteria_name === c.name)
    // AI mapping (evalCriteriaMapping.mappings)에서도 찾기
    const aiRow = (evalCriteriaMapping?.mappings || []).find(m => m.criteria_name === c.name)

    let criteriaId, item
    if (userRow) {
      // case 1: backend row 있음 — 그 ID + 데이터 사용
      criteriaId = userRow.criteria_id
      item = userRow
    } else if (aiRow) {
      // case 2: AI mapping만 있음 — 결정적 ID 생성 + AI 데이터 사용
      criteriaId = generateCriteriaId({ sessionId, criteriaName: c.name })
      item = {
        criteria_id: criteriaId,
        criteria_name: c.name,
        weight: c.score || 0,
        scope: aiRow.scope || 'section',
        mapped_questions: (aiRow.mapped_questions || []).map(mq =>
          typeof mq === 'string' ? mq : (mq.question_id || mq.qid)
        ).filter(Boolean),
        mapping_type: aiRow.mapping_type || 'direct',
        confidence: aiRow.confidence ?? 0.5,
        mapped_by: 'ai',
        history_count: 0,
      }
    } else {
      // case 3 (드문 케이스): AI mapping도 없음 — c.mappings에서 추출
      criteriaId = generateCriteriaId({ sessionId, criteriaName: c.name })
      item = {
        criteria_id: criteriaId,
        criteria_name: c.name,
        weight: c.score || 0,
        scope: c.mappings?.[0]?.scope || 'section',
        mapped_questions: (c.mappings || []).map(m => m.qid).filter(Boolean),
        mapping_type: 'direct',
        confidence: c.mappings?.[0]?.conf ?? 0.5,
        mapped_by: 'ai',
        history_count: 0,
      }
    }
    setEditingCriteria({ criteriaId, item })
  }

  // PATCH 성공 후 state 갱신 (응답 item 전체로 교체, history 보존)
  const handleEditSaved = (responseItem) => {
    setUserMappingItems(prev => {
      const idx = prev.findIndex(u => u.criteria_id === responseItem.criteria_id)
      if (idx === -1) return [responseItem, ...prev]
      const next = [...prev]
      next[idx] = responseItem
      return next
    })
    // mergeEvalCriteriaMappings은 evalCriteriaMapping 기준이라
    // 사용자 편집 결과를 evalCriteriaMapping에도 반영해 Tab1 카드에 즉시 표시
    setEvalCriteriaMapping(prev => {
      const mappings = [...(prev?.mappings || [])]
      const idx = mappings.findIndex(m => m.criteria_name === responseItem.criteria_name)
      const merged = {
        criteria_id: responseItem.criteria_id,
        criteria_name: responseItem.criteria_name,
        weight: responseItem.weight,
        scope: responseItem.scope,
        mapped_questions: responseItem.mapped_questions || [],
        mapping_type: responseItem.mapping_type,
        confidence: responseItem.confidence,
        mapped_by: responseItem.mapped_by,
      }
      if (idx === -1) mappings.push(merged)
      else mappings[idx] = merged
      return { ...(prev || {}), mappings, total: mappings.length }
    })
    setEditingCriteria(null)
  }

  // Phase 4-G-7a: SupplementalPanel → mapping pipeline 재실행 트리거
  const refreshAfterMissing = () => {
    setMappingFetched(false)  // useEffect 재실행
  }
  // post-fix 1: 부모 setter 호출만 (Step 2 ↔ 3 ↔ 4 이동 시 손실 방지)
  const handleSupplementalChange = (item) => {
    onSupplementalChangeLifted?.(item)
  }

  // ─── form_prd/4.md + 5.md: FormQuestion 편집/추가/제외 ───
  // toast: 저장 성공/실패 알림 (간단 inline toast)
  const [toast, setToast] = useState(null)
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 4000)
    return () => clearTimeout(t)
  }, [toast])

  const [editorState, setEditorState] = useState({
    open: false, mode: 'edit', question: null, sectionId: null, sectionTitle: '',
    insertPosition: null,  // 2026-05-18: add 시 {before|after: qid}
  })
  const [editorBusy, setEditorBusy] = useState(false)
  const [editorError, setEditorError] = useState(null)
  // 2026-05-18: question move modal state
  const [moveModalState, setMoveModalState] = useState({ open: false, questionId: null, currentSectionId: null })
  // 2026-05-18: "↻ 양식 다시 분석" 클릭 시 모드 선택 모달
  const [reanalyzeModalState, setReanalyzeModalState] = useState({ open: false, selectedMode: 'hybrid' })

  // backend 원본 question 객체 찾기 (formApiResp 기준 — adaptFormFromApi가 아닌 원본)
  const findBackendQuestion = useCallback((qid) => {
    if (!formApiResp?.sections) return null
    for (const sec of formApiResp.sections) {
      for (const q of (sec.questions || [])) {
        if (q.question_id === qid) return q
      }
    }
    return null
  }, [formApiResp])

  const openEditModal = useCallback((qid) => {
    const q = findBackendQuestion(qid)
    if (!q) return
    setEditorError(null)
    setEditorState({ open: true, mode: 'edit', question: q, sectionId: null, sectionTitle: '' })
  }, [findBackendQuestion])

  const openAddModal = useCallback((sectionId) => {
    const sec = (formApiResp?.sections || []).find(s => s.section_id === sectionId)
    setEditorError(null)
    setEditorState({ open: true, mode: 'add', question: null, sectionId, sectionTitle: sec?.title || '', insertPosition: null })
  }, [formApiResp])

  // 2026-05-18: 문항 위/아래에 추가
  const openAddAboveModal = useCallback((sectionId, beforeQid) => {
    const sec = (formApiResp?.sections || []).find(s => s.section_id === sectionId)
    setEditorError(null)
    setEditorState({
      open: true, mode: 'add', question: null,
      sectionId, sectionTitle: sec?.title || '',
      insertPosition: { before: beforeQid },
    })
  }, [formApiResp])
  const openAddBelowModal = useCallback((sectionId, afterQid) => {
    const sec = (formApiResp?.sections || []).find(s => s.section_id === sectionId)
    setEditorError(null)
    setEditorState({
      open: true, mode: 'add', question: null,
      sectionId, sectionTitle: sec?.title || '',
      insertPosition: { after: afterQid },
    })
  }, [formApiResp])

  const closeEditor = useCallback(() => {
    if (editorBusy) return
    setEditorState(s => ({ ...s, open: false }))
  }, [editorBusy])

  // PATCH 성공 응답 → state/cache 갱신 공통 처리
  // 5.md 추가 요구: PATCH 성공 후에만 state/cache 갱신
  // 5.md 추가 요구: cache는 mapping/missing/eval/evidence/company 5개만 제거, notice/form 유지
  const applyPatchSuccess = useCallback((updatedSchema) => {
    if (!updatedSchema) return
    setFormApiResp(updatedSchema)
    const adapted = adaptFormFromApi(updatedSchema)
    setFormData(adapted)
    // downstream stale data 제거 (state)
    setMappingResult(null)
    setMissingMaterials(null)
    setEvalCriteriaMapping(null)
    setEvidenceData(null)
    setCompanyData(null)
    setMappingFetched(false)  // 자동 매핑 useEffect 재실행 게이트
    // cache 부분 갱신: formApiResp/formData만 갱신, downstream 5개는 제거 (notice는 유지)
    if (sessionId) {
      const prev = readStep2Cache(sessionId) || {}
      const next = { ...prev, formApiResp: updatedSchema, formData: adapted }
      delete next.mappingResult
      delete next.missingMaterials
      delete next.evalCriteriaMapping
      delete next.evidenceData
      delete next.companyData
      try {
        sessionStorage.setItem(STEP2_CACHE_KEY_PREFIX + sessionId, JSON.stringify(next))
      } catch (err) {
        console.warn('[STEP2_CACHE_PARTIAL_WRITE_FAILED]', err)
      }
    }
  }, [sessionId])

  const submitEditor = useCallback(async (payload) => {
    setEditorBusy(true)
    setEditorError(null)
    try {
      let res
      if (editorState.mode === 'edit') {
        const qid = editorState.question?.question_id
        if (!qid) throw new Error('question_id 없음')
        res = await analysisApi.patchFormSchemaQuestion({
          sessionId, action: 'update', questionId: qid, payload,
        })
      } else {
        if (!editorState.sectionId) throw new Error('section_id 없음')
        res = await analysisApi.patchFormSchemaQuestion({
          sessionId, action: 'add', sectionId: editorState.sectionId, payload,
          insertPosition: editorState.insertPosition,  // 2026-05-18
        })
      }
      if (!res?.saved || !res?.updated_schema) {
        throw new Error('서버가 saved=true / updated_schema를 반환하지 않음')
      }
      // 성공 시에만 state/cache 갱신
      applyPatchSuccess(res.updated_schema)
      setEditorState(s => ({ ...s, open: false }))
      setToast('문항이 저장되었습니다 — 매핑/부족자료 재분석이 필요합니다')
    } catch (err) {
      console.warn('[patchFormSchemaQuestion]', err)
      setEditorError(err.message || '저장 실패')
    } finally {
      setEditorBusy(false)
    }
  }, [editorState, sessionId, applyPatchSuccess])

  const toggleExclude = useCallback(async (qid, nextExcluded) => {
    if (!sessionId) return
    try {
      const res = await analysisApi.patchFormSchemaQuestion({
        sessionId, action: 'exclude', questionId: qid, excluded: !!nextExcluded,
      })
      if (!res?.saved || !res?.updated_schema) {
        throw new Error('서버가 saved=true / updated_schema를 반환하지 않음')
      }
      applyPatchSuccess(res.updated_schema)
      setToast(nextExcluded
        ? '문항을 트리에서 제외했습니다 (v0.1: 매핑/초안 제외는 후속)'
        : '문항 제외를 해제했습니다')
    } catch (err) {
      console.warn('[toggleExclude]', err)
      setToast(`제외 처리 실패: ${err.message || err}`)
    }
  }, [sessionId, applyPatchSuccess])

  // ─────────────────────────────────────────────────────────
  // 2026-05-18: Tree CRUD 신규 핸들러
  // ─────────────────────────────────────────────────────────

  // Question 영구 삭제 (DB)
  const handleDeleteQuestion = useCallback(async (qid) => {
    if (!sessionId) return
    if (!window.confirm(`문항 "${qid}"을 영구 삭제합니다.\n복구 불가합니다. 계속할까요?`)) return
    try {
      const res = await analysisApi.patchFormSchemaQuestion({
        sessionId, action: 'delete', questionId: qid,
      })
      if (!res?.saved || !res?.updated_schema) throw new Error('saved=false')
      applyPatchSuccess(res.updated_schema)
      setToast(`문항 ${qid} 삭제 완료`)
    } catch (err) {
      console.warn('[deleteQuestion]', err)
      setToast(`삭제 실패: ${err.message || err}`)
    }
  }, [sessionId, applyPatchSuccess])

  // Question 다른 section으로 이동 — modal 열기
  const openMoveQuestionModal = useCallback((qid, currentSid) => {
    setMoveModalState({ open: true, questionId: qid, currentSectionId: currentSid })
  }, [])
  const submitMoveQuestion = useCallback(async (targetSectionId) => {
    const { questionId } = moveModalState
    if (!sessionId || !questionId || !targetSectionId) return
    setMoveModalState({ open: false, questionId: null, currentSectionId: null })
    try {
      const res = await analysisApi.patchFormSchemaQuestion({
        sessionId, action: 'move', questionId, targetSectionId,
      })
      if (!res?.saved || !res?.updated_schema) throw new Error('saved=false')
      applyPatchSuccess(res.updated_schema)
      setToast(`문항 ${questionId} → ${targetSectionId} 이동 완료`)
    } catch (err) {
      console.warn('[moveQuestion]', err)
      setToast(`이동 실패: ${err.message || err}`)
    }
  }, [sessionId, moveModalState, applyPatchSuccess])

  // Section 추가 (트리 상단 + 섹션 추가 버튼)
  const handleAddSection = useCallback(async () => {
    if (!sessionId) return
    const title = window.prompt('새 섹션 제목을 입력하세요')
    if (!title || !title.trim()) return
    try {
      const res = await analysisApi.patchFormSchemaSection({
        sessionId, action: 'add', payload: { title: title.trim() },
      })
      if (!res?.saved || !res?.updated_schema) throw new Error('saved=false')
      applyPatchSuccess(res.updated_schema)
      setToast(`섹션 추가됨: ${res.message || ''}`)
    } catch (err) {
      console.warn('[addSection]', err)
      setToast(`섹션 추가 실패: ${err.message || err}`)
    }
  }, [sessionId, applyPatchSuccess])

  // Section 이름 수정
  const handleRenameSection = useCallback(async (sid) => {
    if (!sessionId) return
    const sec = (formApiResp?.sections || []).find(s => s.section_id === sid)
    const currentTitle = sec?.title || ''
    const newTitle = window.prompt('섹션 새 제목', currentTitle)
    if (!newTitle || !newTitle.trim() || newTitle.trim() === currentTitle) return
    try {
      const res = await analysisApi.patchFormSchemaSection({
        sessionId, action: 'rename', sectionId: sid, payload: { title: newTitle.trim() },
      })
      if (!res?.saved || !res?.updated_schema) throw new Error('saved=false')
      applyPatchSuccess(res.updated_schema)
      setToast(`섹션 ${sid} 이름 변경 완료`)
    } catch (err) {
      console.warn('[renameSection]', err)
      setToast(`이름 변경 실패: ${err.message || err}`)
    }
  }, [sessionId, formApiResp, applyPatchSuccess])

  // Section 삭제 (하위 question 있으면 confirm force)
  const handleDeleteSection = useCallback(async (sid) => {
    if (!sessionId) return
    const sec = (formApiResp?.sections || []).find(s => s.section_id === sid)
    const qCount = (sec?.questions || []).length
    let force = false
    if (qCount > 0) {
      if (!window.confirm(`섹션 "${sec?.title}"에 문항 ${qCount}개가 있습니다.\n섹션과 모든 문항을 함께 삭제할까요?`)) return
      force = true
    } else {
      if (!window.confirm(`섹션 "${sec?.title}"을 삭제할까요?`)) return
    }
    try {
      const res = await analysisApi.patchFormSchemaSection({
        sessionId, action: 'delete', sectionId: sid, force,
      })
      if (!res?.saved || !res?.updated_schema) throw new Error('saved=false')
      applyPatchSuccess(res.updated_schema)
      setToast(`섹션 ${sid} 삭제 완료`)
    } catch (err) {
      console.warn('[deleteSection]', err)
      setToast(`삭제 실패: ${err.message || err}`)
    }
  }, [sessionId, formApiResp, applyPatchSuccess])

  // Section 순서 변경 (up/down 1칸)
  const handleReorderSection = useCallback(async (sid, direction) => {
    if (!sessionId) return
    const sections = formApiResp?.sections || []
    const currentIdx = sections.findIndex(s => s.section_id === sid)
    if (currentIdx < 0) return
    const targetIdx = direction === 'up' ? currentIdx - 1 : currentIdx + 1
    if (targetIdx < 0 || targetIdx >= sections.length) return
    try {
      const res = await analysisApi.patchFormSchemaSection({
        sessionId, action: 'reorder', sectionId: sid, targetIndex: targetIdx,
      })
      if (!res?.saved || !res?.updated_schema) throw new Error('saved=false')
      applyPatchSuccess(res.updated_schema)
      setToast(`섹션 ${sid} ${direction === 'up' ? '↑' : '↓'} 이동 완료`)
    } catch (err) {
      console.warn('[reorderSection]', err)
      setToast(`순서 변경 실패: ${err.message || err}`)
    }
  }, [sessionId, formApiResp, applyPatchSuccess])


  useEffect(() => {
    // form_prd/6.md: parse-notice auto-trigger 게이트 강화
    //   - restoreChecked=false: getSession 응답 아직 안 옴 → 기다림 (race condition 방지)
    //   - restoredNoticeSchema 존재: DB 복원 예정 (sync useEffect가 처리) → skip
    //   - noticeFetched=true: 이미 분석됨 → skip
    //   - sessionId 없음: offline → skip
    if (!restoreChecked) return
    if (restoredNoticeSchema) return
    if (noticeFetched) return
    if (!sessionId) return
    // post-fix 3: notice도 uploads도 비어있어도 호출 (mock은 텍스트 무관 응답)
    // 빈 string인 경우 placeholder 사용. 실제 LLM 시점엔 사용자에게 안내 추가 예정.
    const noticeText = extractNoticeText(notice, uploads) || '[v0.2 mock — notice text not provided]'

    setNoticeLoading(true)
    setNoticeError(null)
    analysisApi.parseNotice({ sessionId, noticeText })
      .then(res => {
        logApi('parse-notice raw', {
          target: !!res?.target,
          benefit: !!res?.benefit,
          eval_criteria: res?.evaluation_criteria?.length || 0,
          required_documents: res?.required_documents?.length || 0,
        })
        setNoticeApiResp(res)
        const adapted = adaptNoticeFromApi(res)
        logApi('parse-notice adapted', {
          fact: adapted.fact.length,
          eval_criteria: adapted.evaluation_criteria.length,
        })
        setNoticeData(adapted)
        setNoticeFetched(true)
        writeStep2Cache(sessionId, { noticeApiResp: res, noticeData: adapted })
      })
      .catch(err => {
        handleFallback('parse-notice', err, {
          onError: (msg) => setNoticeError(msg),
        })
        setNoticeError(err.message || '알 수 없는 오류')
        setNoticeFetched(true)
      })
      .finally(() => setNoticeLoading(false))
  }, [sessionId, notice, uploads, noticeFetched, restoreChecked, restoredNoticeSchema])

  // 2026-05-18: form_parser 모드 선택 (single | hybrid)
  // localStorage에 마지막 선택 저장 → 다음 session에서도 유지
  const [parserMode, setParserMode] = useState(() => {
    try {
      const saved = localStorage.getItem('ajin_v2_form_parser_mode')
      return saved === 'hybrid' || saved === 'single' ? saved : 'hybrid'  // default hybrid
    } catch (_) {
      return 'hybrid'
    }
  })
  const updateParserMode = useCallback((mode) => {
    setParserMode(mode)
    try { localStorage.setItem('ajin_v2_form_parser_mode', mode) } catch (_) { /* ignore */ }
  }, [])

  // form/evidence/company 병렬 호출 — Tab2 "제출양식 분석 시작" 버튼에서 명시 호출 (자동 트리거 없음)
  const runFormAnalysis = useCallback((modeOverride) => {
    if (!sessionId) return
    if (!noticeApiResp) return  // notice 분석 완료 후만 가능

    // 2026-05-19: safety — onClick 등으로 인해 event 객체가 modeOverride로 들어올 가능성 차단
    //   (JSON.stringify(MouseEvent) → Converting circular structure to JSON)
    const safeMode = (typeof modeOverride === 'string') ? modeOverride : null
    const effectiveMode = safeMode || parserMode

    // 업로드된 양식 파일이 있으면 빈 문자열 → backend가 session.attachments(kind=form)에서 자동 추출
    const formNames = uploads?.formFiles?.map(f => f.name).join(', ') || '사업계획서.pdf'
    const formText = uploads?.formFiles?.length
      ? ''
      : `[제출양식 파일] ${formNames}\n${notice?.title || ''}`
    const refNames = uploads?.references?.map(f => f.name).join(', ') || ''
    const refText = refNames ? `[참고자료] ${refNames}` : 'no reference text'

    setFormLoading(true)
    setFormError(null)

    Promise.allSettled([
      analysisApi.parseForm({ sessionId, formText, formName: formNames, parserMode: effectiveMode }),
      analysisApi.extractEvidence({ sessionId, refText, sourceFile: refNames }),
      analysisApi.analyzeCompany({ sessionId, companyFiles: [], noticeSchema: noticeApiResp || {} }),
    ]).then(([formRes, evidenceRes, companyRes]) => {
      // parse-form
      if (formRes.status === 'fulfilled') {
        logApi('parse-form raw', { sections: formRes.value?.sections?.length || 0 })
        setFormApiResp(formRes.value)
        const adapted = adaptFormFromApi(formRes.value)
        logApi('parse-form adapted', adapted.stats)
        setFormData(adapted)
        writeStep2Cache(sessionId, { formApiResp: formRes.value, formData: adapted })
      } else {
        handleFallback('parse-form', formRes.reason, {
          onError: (msg) => setFormError(msg),
          onClear: () => setFormData({ stats: { total: 0, sections: 0, tables: 0 }, sections: [] }),
        })
      }
      // extract-evidence
      if (evidenceRes.status === 'fulfilled') {
        logApi('extract-evidence raw', { items: evidenceRes.value?.items?.length || 0 })
        setEvidenceData(evidenceRes.value)
        writeStep2Cache(sessionId, { evidenceData: evidenceRes.value })
      } else {
        handleFallback('extract-evidence', evidenceRes.reason)
      }
      // analyze-company
      if (companyRes.status === 'fulfilled') {
        logApi('analyze-company raw', {
          has_company: !!companyRes.value?.company,
          has_fit: !!companyRes.value?.fit_analysis,
        })
        setCompanyData(companyRes.value)
        writeStep2Cache(sessionId, { companyData: companyRes.value })
      } else {
        handleFallback('analyze-company', companyRes.reason)
      }
      setFormFetched(true)
      setFormLoading(false)
    })
  }, [sessionId, noticeApiResp, uploads, notice, parserMode])

  // Tab2 "↻ 다시 분석" — 기존 결과 리셋 + 재실행
  // 2026-05-18: modeOverride 인자 추가 — 모달에서 선택한 모드로 실행
  const resetAndRunFormAnalysis = useCallback((modeOverride) => {
    setFormApiResp(null)
    setFormData(EMPTY_FORM)
    setEvidenceData(null)
    setCompanyData(null)
    setFormError(null)
    setFormFetched(false)
    setMappingResult(null)
    setMissingMaterials(null)
    setMappingFetched(false)
    writeStep2Cache(sessionId, {
      formApiResp: null, formData: null,
      evidenceData: null, companyData: null,
    })
    runFormAnalysis(modeOverride)
  }, [runFormAnalysis, sessionId])

  // 2026-05-18: 모달에서 "분석 시작" 클릭 시 호출
  const submitReanalyze = useCallback(() => {
    const mode = reanalyzeModalState.selectedMode
    setReanalyzeModalState({ open: false, selectedMode: 'hybrid' })
    // parserMode state도 업데이트 (다음 분석에서 default로 사용)
    updateParserMode(mode)
    resetAndRunFormAnalysis(mode)
  }, [reanalyzeModalState.selectedMode, resetAndRunFormAnalysis])

  // C-2 (b8.md §1): 자동 매핑 useEffect 제거.
  //   기존 자동 트리거 useEffect는 step2_confirmed 게이트 도입(C-2) 이후 호환되지 않음
  //   (step2 확정 전 호출 시 backend가 409 반환).
  //   대신 runMappingPipeline()으로 추출만. 호출은 C-3 (사용자 명시 trigger)에서 수행.
  const runMappingPipeline = useCallback(async () => {
    if (!sessionId) return
    if (!formApiResp) return

    const evidenceList = evidenceData?.items || []

    // 1) map-evidence + 2) check-missing
    try {
      const mapRes = await analysisApi.mapEvidence({
        sessionId,
        formSchema: formApiResp,
        evidenceList,
        noticeSchema: noticeApiResp || {},
      })
      logApi('map-evidence raw', {
        question_mappings: mapRes?.question_mappings?.length || 0,
        coverage_rate: mapRes?.coverage_rate,
        missing_count: mapRes?.overall_missing_count,
      })
      setMappingResult(mapRes)
      const mRes = await analysisApi.checkMissing({ sessionId, mappingResult: mapRes })
      const missingCount = Array.isArray(mRes) ? mRes.length : (mRes?.items?.length || 0)
      logApi('check-missing raw', { missing: missingCount })
      setMissingMaterials(mRes)
    } catch (err) {
      handleFallback('mapping pipeline', err)
    }

    // 3) map-eval-criteria (parse-notice 결과 + parse-form 결과)
    if (noticeApiResp) {
      try {
        const res = await analysisApi.mapEvalCriteria({
          sessionId,
          noticeSchema: noticeApiResp,
          formSchema: formApiResp,
        })
        logApi('map-eval-criteria raw', {
          mappings: res?.mappings?.length || 0,
          total: res?.total,
        })
        setEvalCriteriaMapping(res)
      } catch (err) {
        handleFallback('map-eval-criteria', err)
      }
    }

    setMappingFetched(true)
  }, [sessionId, formApiResp, evidenceData, noticeApiResp])

  // Phase 4-G-6: 분석 완료 시 부모(DraftPageV2)에 step2Data 전달 (Step 3에서 사용)
  useEffect(() => {
    if (!onAnalysisReady) return
    if (!formApiResp || !noticeApiResp) return
    onAnalysisReady({
      formApiResp,
      formData: applyStatusToForm(formData, mappingResult, missingMaterials),
      noticeApiResp,
      noticeData,
      mappingResult,
      missingMaterials,
      evidenceData,
      companyData,
      evalCriteriaMapping,
      supplementalMaterials,  // Phase 4-G-7a R7: 누적된 supplemental 목록
    })
  }, [formApiResp, noticeApiResp, formData, noticeData, mappingResult, missingMaterials, evidenceData, companyData, evalCriteriaMapping, supplementalMaterials, onAnalysisReady])

  const noticeTitle = notice?.title || noticeApiResp?.notice_title || noticeApiResp?.title || ''

  return (
    <div className="p-6 text-base">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-4">
        <div className="min-w-0 flex-1 mr-4">
          <h2 className="text-3xl font-bold text-slate-900">Step 2. 분석</h2>
          {noticeTitle && (
            <p className="text-lg font-semibold text-indigo-900 mt-1 truncate" title={noticeTitle}>
              📋 {noticeTitle}
            </p>
          )}
          <p className="text-base text-slate-500 mt-1">공고문과 제출양식을 분석하고 매칭 결과를 확인합니다</p>
        </div>
        <button
          onClick={onToggleDevMode}
          className="px-3 py-1.5 text-base border border-slate-200 rounded hover:bg-slate-50 transition shrink-0"
        >
          🛠 개발자 모드
        </button>
      </div>

      {/* 탭 */}
      <div className="flex gap-1 border-b border-slate-200 mb-4">
        <button
          onClick={() => setActiveTab('notice')}
          className={`px-4 py-2.5 text-base transition border-b-2 -mb-px ${
            activeTab === 'notice'
              ? 'border-slate-900 text-slate-900 font-semibold'
              : 'border-transparent text-slate-500 hover:text-slate-900'
          }`}
        >
          <span className="font-mono text-xs text-slate-400 mr-2">01</span>
          공고문 분석
        </button>
        <button
          onClick={() => setActiveTab('form')}
          className={`px-4 py-2.5 text-base transition border-b-2 -mb-px ${
            activeTab === 'form'
              ? 'border-slate-900 text-slate-900 font-semibold'
              : 'border-transparent text-slate-500 hover:text-slate-900'
          }`}
        >
          <span className="font-mono text-xs text-slate-400 mr-2">02</span>
          제출양식 분석
        </button>
      </div>

      {/* 패널 */}
      {activeTab === 'notice' && (
        <Tab1NoticeAnalysis
          noticeData={mergeEvalCriteriaMappings(noticeData, evalCriteriaMapping)}
          loading={noticeLoading}
          error={noticeError}
          onEditCriteria={sessionId ? handleEditCriteria : null}
          userEditedNames={userEditedNames}
          onReanalyze={sessionId ? () => {
            // notice 상태 reset → useEffect가 parse-notice 재호출
            setNoticeApiResp(null)
            setNoticeData(EMPTY_NOTICE)
            setNoticeError(null)
            setNoticeFetched(false)
            writeStep2Cache(sessionId, { noticeApiResp: null, noticeData: null })
          } : null}
          onConfirm={onConfirmStep2 || null}
        />
      )}

      {/* v0.2.1 V3: 평가기준 매핑 편집 모달 */}
      <EvalCriteriaMappingEditModal
        open={!!editingCriteria}
        sessionId={sessionId}
        criteriaId={editingCriteria?.criteriaId}
        criteriaItem={editingCriteria?.item}
        formData={formData}
        validQuestionIds={validQuestionIds}
        onClose={() => setEditingCriteria(null)}
        onSaved={handleEditSaved}
      />
      {activeTab === 'form' && (
        <Tab2FormPreview
          formData={applyStatusToForm(formData, mappingResult, missingMaterials)}
          formApiResp={formApiResp}
          loading={formLoading}
          error={formError}
          sessionId={sessionId}
          formFileId={uploads?.formFiles?.[0]?.file_id || null}
          formFileName={uploads?.formFiles?.[0]?.name || ''}
          missingMaterials={missingMaterials}
          mappingResult={mappingResult}
          onMissingChange={refreshAfterMissing}
          onSupplementalChange={handleSupplementalChange}
          supplementalMaterials={supplementalMaterials}
          hasResult={!!formApiResp}
          canStart={!!sessionId && !!noticeApiResp}
          onStart={runFormAnalysis}
          onReanalyze={() => setReanalyzeModalState({ open: true, selectedMode: parserMode })}
          onConfirm={onConfirmStep2 || null}
          parserMode={parserMode}
          onParserModeChange={updateParserMode}
          onEditQuestion={sessionId ? openEditModal : null}
          onAddSection={sessionId ? handleAddSection : null}
          onRenameSection={sessionId ? handleRenameSection : null}
          onDeleteSection={sessionId ? handleDeleteSection : null}
          onReorderSection={sessionId ? handleReorderSection : null}
          onAddAboveQuestion={sessionId ? openAddAboveModal : null}
          onAddBelowQuestion={sessionId ? openAddBelowModal : null}
          onDeleteQuestion={sessionId ? handleDeleteQuestion : null}
          onMoveQuestion={sessionId ? openMoveQuestionModal : null}
          onAddInSection={sessionId ? openAddModal : null}
          onToggleExclude={sessionId ? toggleExclude : null}
        />
      )}

      {/* form_prd/4.md + 5.md: FormQuestion 편집/추가 모달 */}
      <FormQuestionEditor
        open={editorState.open}
        mode={editorState.mode}
        question={editorState.question}
        sectionId={editorState.sectionId}
        sectionTitle={editorState.sectionTitle}
        busy={editorBusy}
        onClose={closeEditor}
        onSubmit={submitEditor}
      />

      {/* 2026-05-18: Question 이동 — 섹션 선택 모달 */}
      {moveModalState.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4"
          onClick={() => setMoveModalState({ open: false, questionId: null, currentSectionId: null })}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full" onClick={(e) => e.stopPropagation()}>
            <div className="px-6 py-4 border-b border-slate-200">
              <h3 className="text-base font-semibold text-slate-900">
                문항 이동 — {moveModalState.questionId}
              </h3>
              <p className="text-xs text-slate-500 mt-1">대상 섹션을 선택하세요</p>
            </div>
            <div className="p-4 max-h-[60vh] overflow-y-auto space-y-1">
              {(formApiResp?.sections || []).map((sec) => {
                const isCurrent = sec.section_id === moveModalState.currentSectionId
                return (
                  <button
                    key={sec.section_id}
                    type="button"
                    disabled={isCurrent}
                    onClick={() => submitMoveQuestion(sec.section_id)}
                    className={`w-full text-left px-3 py-2 rounded text-sm border transition ${
                      isCurrent
                        ? 'border-slate-200 bg-slate-100 text-slate-400 cursor-not-allowed'
                        : 'border-slate-200 hover:border-indigo-500 hover:bg-indigo-50 text-slate-900'
                    }`}
                  >
                    <span className="font-mono text-xs text-slate-400 mr-2">{sec.section_id}</span>
                    {sec.title}
                    {isCurrent && <span className="ml-2 text-[10px] text-slate-400">(현재)</span>}
                    <span className="ml-2 text-[10px] text-slate-400">{(sec.questions || []).length}문항</span>
                  </button>
                )
              })}
            </div>
            <div className="px-4 py-3 border-t border-slate-200 flex justify-end">
              <button
                type="button"
                onClick={() => setMoveModalState({ open: false, questionId: null, currentSectionId: null })}
                className="text-sm px-3 py-1.5 border border-slate-200 rounded hover:bg-slate-50"
              >취소</button>
            </div>
          </div>
        </div>
      )}
      {/* 2026-05-18: "↻ 양식 다시 분석" 모드 선택 모달 */}
      {reanalyzeModalState.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4"
          onClick={() => setReanalyzeModalState({ open: false, selectedMode: parserMode })}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full" onClick={(e) => e.stopPropagation()}>
            <div className="px-6 py-4 border-b border-slate-200">
              <h3 className="text-base font-semibold text-slate-900">양식 다시 분석</h3>
              <p className="text-xs text-slate-500 mt-1">분석 모드를 선택하세요. 기존 결과는 덮어씌워집니다.</p>
            </div>
            <div className="p-4 space-y-2">
              <label className="flex items-start gap-2 p-3 border rounded cursor-pointer hover:bg-slate-50 transition border-slate-200 has-[:checked]:border-indigo-500 has-[:checked]:bg-indigo-50/50">
                <input
                  type="radio"
                  name="reanalyze-mode"
                  value="hybrid"
                  checked={reanalyzeModalState.selectedMode === 'hybrid'}
                  onChange={() => setReanalyzeModalState(prev => ({ ...prev, selectedMode: 'hybrid' }))}
                  className="mt-1"
                />
                <div className="flex-1 text-left">
                  <div className="text-sm font-medium text-slate-900">🎯 정밀 분석 (Hybrid, 권장)</div>
                  <div className="text-[11px] text-slate-600 mt-0.5">
                    Regex chapter 분리 → 병렬 LLM. section 일관성 ↑. 약 100~150초, ~30원.
                  </div>
                </div>
              </label>
              <label className="flex items-start gap-2 p-3 border rounded cursor-pointer hover:bg-slate-50 transition border-slate-200 has-[:checked]:border-indigo-500 has-[:checked]:bg-indigo-50/50">
                <input
                  type="radio"
                  name="reanalyze-mode"
                  value="single"
                  checked={reanalyzeModalState.selectedMode === 'single'}
                  onChange={() => setReanalyzeModalState(prev => ({ ...prev, selectedMode: 'single' }))}
                  className="mt-1"
                />
                <div className="flex-1 text-left">
                  <div className="text-sm font-medium text-slate-900">⚡ 빠른 분석 (Single)</div>
                  <div className="text-[11px] text-slate-600 mt-0.5">
                    단일 LLM 호출. 짧은 form 적합. 38p+ 긴 form은 section 누락 가능. 약 60~120초, ~3원.
                  </div>
                </div>
              </label>
            </div>
            <div className="px-4 py-3 border-t border-slate-200 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setReanalyzeModalState({ open: false, selectedMode: parserMode })}
                className="text-sm px-3 py-1.5 border border-slate-200 rounded hover:bg-slate-50"
              >취소</button>
              <button
                type="button"
                onClick={submitReanalyze}
                className="text-sm px-4 py-1.5 bg-indigo-950 text-white rounded hover:bg-indigo-900"
              >📄 분석 시작</button>
            </div>
          </div>
        </div>
      )}
      {editorError && editorState.open && (
        <div className="fixed bottom-6 right-6 z-[60] bg-rose-50 border border-rose-300 text-rose-900 text-sm px-4 py-2 rounded shadow-lg">
          ⚠ {editorError}
        </div>
      )}
      {/* toast (form 수정 후 안내) */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[60] bg-slate-900 text-white text-sm px-4 py-2 rounded shadow-lg">
          {toast}
        </div>
      )}

      {/* Step 2 요약 정보 (Tab별 stats + hint)
          formApiResp 없으면 formDataForStats=null → Tab2 footer/Diagnostic 모두 '—' 표시 (Tab1 동일 패턴) */}
      {(() => {
        const formDataForStats = formApiResp
          ? applyStatusToForm(formData, mappingResult, missingMaterials)
          : null
        return (
          <>
            <Step2SummaryPanel
              stats={activeTab === 'notice' ? buildTab1FooterStats(noticeApiResp) : buildTab2FooterStats(formDataForStats)}
              hint={activeTab === 'notice' ? TAB1_FOOTER_HINT : TAB2_FOOTER_HINT}
            />
            <Step2QualityDiagnostic
              noticeApiResp={noticeApiResp}
              formData={formDataForStats}
              evalCriteriaMapping={evalCriteriaMapping}
              mappingResult={mappingResult}
              missingMaterials={missingMaterials}
              validQuestionIds={validQuestionIds}
            />
          </>
        )
      })()}

      {/* 네비게이션 바 (좌끝 이전 / 우끝 확정) */}
      <StepNavigationBar
        onPrev={onPrev}
        onNext={onConfirmStep2}
        prevLabel="← 이전 (Step 1)"
        nextLabel="Step 2 분석 결과 확정 →"
        nextVariant="confirm"
      />
    </div>
  )
}
