// AJIN BizAI v0.2.1 QG-1 — Step 2 Footer Quality Diagnostic
//
// Quality Gate가 아니라 Quality Diagnostic.
// 통과/조건부/검토/실패 자동 판정 없음. 수치 + 위험 신호 텍스트만 표시.
//
// 3 export 함수:
//   - computeStep2QualityMetrics({ noticeApiResp, formData, evalCriteriaMapping,
//                                  mappingResult, missingMaterials, validQuestionIds })
//   - detectStep2RiskSignals(metrics)
//   - getRiskBadgeMeta({ riskCount, isLoading, hasData })

// ─── 상수 ────────────────────────────────────────────────────────

const STATUS_OK_TYPES = new Set(['ok'])
const STATUS_WEAK_TYPES = new Set(['weak'])
const STATUS_MISSING_TYPES = new Set(['missing'])

// 위험 신호 표시 정책
const MAX_DISPLAYED_SIGNALS = 3

// ─── helpers ─────────────────────────────────────────────────────

function isBlank(v) {
  if (v == null) return true
  if (typeof v === 'string') return v.trim() === ''
  return false
}

function normalizeName(n) {
  return String(n || '').trim().replace(/\s+/g, ' ').toLowerCase()
}

/**
 * evalCriteriaMapping.mappings를 criteria_id + criteria_name 기준 dedup.
 * V3 mergeEvalCriteriaMappings와 같은 패턴 — single source라 단순 dedup만.
 */
function dedupEvalCriteria(mappings) {
  if (!Array.isArray(mappings)) return []
  const seenById = new Set()
  const seenByName = new Set()
  const out = []
  for (const m of mappings) {
    if (!m) continue
    if (m.criteria_id && seenById.has(m.criteria_id)) continue
    const name = normalizeName(m.criteria_name)
    if (name && seenByName.has(name)) continue
    if (m.criteria_id) seenById.add(m.criteria_id)
    if (name) seenByName.add(name)
    out.push(m)
  }
  return out
}

function extractMappedQids(mapped_questions) {
  if (!Array.isArray(mapped_questions)) return []
  const out = []
  for (const mq of mapped_questions) {
    if (typeof mq === 'string') out.push(mq)
    else if (mq?.question_id) out.push(mq.question_id)
    else if (mq?.qid) out.push(mq.qid)
  }
  return out
}

// ─── 1. computeStep2QualityMetrics ──────────────────────────────

/**
 * 11 metric 계산.
 *
 * 반환 dict:
 *   questionCount, okCount, weakCount, missingCount,
 *   sufficiencyPercent (null = 데이터 없음),
 *   evalCriteriaCount, evalCriteriaWeightSum,
 *   requiredDocsCount,
 *   sourcePageMissingCount, invalidQuestionIdCount, duplicateQuestionIdCount,
 *   hasData, isLoading
 */
export function computeStep2QualityMetrics({
  noticeApiResp = null,
  formData = null,
  evalCriteriaMapping = null,
  mappingResult = null,
  missingMaterials = null,
  validQuestionIds = [],
} = {}) {
  // ── 데이터 상태 판정 ────────────────────────────────────────
  const hasNotice = !!noticeApiResp
  const hasForm = !!(formData?.sections && formData.sections.length > 0)
  const hasData = hasNotice || hasForm
  const isLoading = !hasData     // 둘 다 없으면 분석 중으로 간주

  // ── FormSchema 기반 question 수집 ──────────────────────────
  const allQuestions = []
  const allQuestionIds = []
  let sourcePageMissingCount = 0
  if (hasForm) {
    for (const sec of formData.sections) {
      for (const q of (sec.questions || [])) {
        allQuestions.push(q)
        if (q.id != null) allQuestionIds.push(q.id)
        if (isBlank(q.source_page)) sourcePageMissingCount++
      }
    }
  }
  const questionCount = allQuestionIds.length

  // duplicateQuestionIdCount — Set 비교
  const uniqueIdSet = new Set(allQuestionIds)
  const duplicateQuestionIdCount = allQuestionIds.length - uniqueIdSet.size

  // ── ok / weak / missing 카운트 ─────────────────────────────
  // status가 question 객체에 이미 적용된 경우 (applyStatusToForm 결과)
  // 또는 mappingResult/missingMaterials 기반 자체 계산
  let okCount = 0, weakCount = 0, missingCount = 0
  if (allQuestions.some(q => q.status)) {
    // 이미 status가 question에 있음 (applyStatusToForm 결과)
    for (const q of allQuestions) {
      if (STATUS_MISSING_TYPES.has(q.status)) missingCount++
      else if (STATUS_WEAK_TYPES.has(q.status)) weakCount++
      else if (STATUS_OK_TYPES.has(q.status)) okCount++
      else okCount++   // status 미정의 = ok 처리 (deriveSufficiency와 동일 정책)
    }
  } else if (hasForm) {
    // mapping/missing으로 status 추론
    const missingByQid = {}
    if (Array.isArray(missingMaterials)) {
      for (const mm of missingMaterials) {
        if (mm.question_id) missingByQid[mm.question_id] = mm
      }
    }
    const mappingByQid = {}
    if (mappingResult?.question_mappings) {
      for (const qm of mappingResult.question_mappings) {
        if (qm.question_id) mappingByQid[qm.question_id] = qm
      }
    }
    for (const q of allQuestions) {
      const miss = missingByQid[q.id]
      const map = mappingByQid[q.id]
      if (miss) {
        if (miss.input_type === 'text') weakCount++
        else missingCount++
      } else if (map && map.confidence_score < 0.70) {
        weakCount++
      } else {
        okCount++
      }
    }
  }

  // ── sufficiency % (공식 고정) ──────────────────────────────
  const total = okCount + weakCount + missingCount
  const sufficiencyPercent = total > 0
    ? Math.round(((okCount + weakCount * 0.5) / total) * 100)
    : null

  // ── 평가기준 dedup ────────────────────────────────────────
  // evalCriteriaMapping 우선, 비어있으면 noticeApiResp.evaluation_criteria fallback.
  // (notice_analyst만 끝나고 evalCriteriaMapping이 아직 없을 때 false-positive 방지)
  let dedupedCriteria = dedupEvalCriteria(evalCriteriaMapping?.mappings || [])
  if (dedupedCriteria.length === 0 && Array.isArray(noticeApiResp?.evaluation_criteria)) {
    dedupedCriteria = noticeApiResp.evaluation_criteria.map((c, i) => ({
      criteria_id: `notice_${i}`,
      criteria_name: c.name,
      weight: c.weight ?? 0,
      mapped_questions: [],
    }))
  }
  const evalCriteriaCount = dedupedCriteria.length
  const evalCriteriaWeightSum = dedupedCriteria.reduce(
    (sum, c) => sum + (Number(c.weight) || 0), 0
  )

  // ── invalid question_id 재계산 (현재 evalCriteriaMapping vs validQuestionIds) ──
  const validSet = new Set(validQuestionIds || [])
  let invalidQuestionIdCount = 0
  if (validSet.size > 0) {
    for (const c of dedupedCriteria) {
      for (const qid of extractMappedQids(c.mapped_questions)) {
        if (!validSet.has(qid)) invalidQuestionIdCount++
      }
    }
  }

  // ── 필수서류 수 ───────────────────────────────────────────
  const requiredDocsArr = noticeApiResp?.required_documents
  const requiredDocsCount = Array.isArray(requiredDocsArr) ? requiredDocsArr.length : 0

  return {
    questionCount,
    okCount,
    weakCount,
    missingCount,
    sufficiencyPercent,
    evalCriteriaCount,
    evalCriteriaWeightSum,
    requiredDocsCount,
    sourcePageMissingCount,
    invalidQuestionIdCount,
    duplicateQuestionIdCount,
    hasData,
    isLoading,
    // raw refs (위험 신호 판정용)
    _noticeApiResp: noticeApiResp,
  }
}

// ─── 2. detectStep2RiskSignals ─────────────────────────────────

/**
 * 8 위험 신호 검사.
 * 반환: { signals, displayedSignals, hiddenCount, count }
 *   - signals: 전체 위험 신호 텍스트 배열
 *   - displayedSignals: 최대 3개 표시용
 *   - hiddenCount: signals.length - displayed (0이면 "외 N개" 미표시)
 */
export function detectStep2RiskSignals(metrics) {
  const signals = []
  if (!metrics) return { signals: [], displayedSignals: [], hiddenCount: 0, count: 0 }

  const notice = metrics._noticeApiResp || {}

  // 1. 마감일 정보 없음
  if (notice && isBlank(notice.deadline)) {
    signals.push('마감일 정보 없음')
  }

  // 2. 지원대상 정보 없음
  if (notice && isBlank(notice.target)) {
    signals.push('지원대상 정보 없음')
  }

  // 3. 필수서류 정보 없음 (속성 누락 vs 빈 배열 분리)
  if (notice && notice.required_documents == null) {
    signals.push('필수서류 정보 없음')
  }

  // 4. 평가기준 추출 안 됨
  if (metrics.evalCriteriaCount === 0) {
    signals.push('평가기준 추출 안 됨')
  }

  // 5. 제출양식 문항 0개
  if (metrics.questionCount === 0) {
    signals.push('제출양식 문항 0개')
  }

  // 6. question_id 중복 의심
  if (metrics.duplicateQuestionIdCount > 0) {
    signals.push(`question_id 중복 의심 ${metrics.duplicateQuestionIdCount}개`)
  }

  // 7. invalid question_id 존재
  if (metrics.invalidQuestionIdCount > 0) {
    signals.push(`유효하지 않은 매핑 ${metrics.invalidQuestionIdCount}개`)
  }

  // 8. source_page 누락 존재
  if (metrics.sourcePageMissingCount > 0) {
    signals.push(`source_page 누락 ${metrics.sourcePageMissingCount}개`)
  }

  const displayedSignals = signals.slice(0, MAX_DISPLAYED_SIGNALS)
  const hiddenCount = Math.max(0, signals.length - MAX_DISPLAYED_SIGNALS)

  return {
    signals,
    displayedSignals,
    hiddenCount,
    count: signals.length,
  }
}

// ─── 3. getRiskBadgeMeta ───────────────────────────────────────

/**
 * Badge 메타 — 4 상태.
 *   - no_data:   "데이터 없음" (slate)
 *   - analyzing: "분석 중"     (amber)
 *   - ok:        "위험 신호 없음" (emerald)
 *   - warn:      "위험 신호 N개" (1~2: amber / 3+: rose)
 *
 * 자동 판정 X — 단순 카운트 매핑.
 */
export function getRiskBadgeMeta({ riskCount = 0, isLoading = false, hasData = true } = {}) {
  if (!hasData && !isLoading) {
    return { status: 'no_data', label: '데이터 없음', color: 'slate' }
  }
  if (isLoading) {
    return { status: 'analyzing', label: '분석 중', color: 'amber' }
  }
  if (riskCount === 0) {
    return { status: 'ok', label: '위험 신호 없음', color: 'emerald' }
  }
  const color = riskCount >= 3 ? 'rose' : 'amber'
  return { status: 'warn', label: `위험 신호 ${riskCount}개`, color }
}
