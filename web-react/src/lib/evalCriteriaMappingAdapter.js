// AJIN BizAI v0.2.1 V3 — EvalCriteriaMapping adapter (pure functions)
//
// 8 export 함수:
//   - nameToSlug                       criteriaName → slug (KNOWN 9 + hash fallback, 결정적)
//   - generateCriteriaId               session-scoped criteria_id 생성
//   - normalizeEvalCriteriaMappingItem 단일 item normalize (invalid qid filter)
//   - mergeEvalCriteriaMappings        base + overlay merge (criteria_id → name dedup)
//   - buildEvalCriteriaPatchPayload    PATCH payload (schema allowlist, valid qid only)
//   - validateEvalCriteriaDraft        validation (차단/경고 분류 결과)
//   - isDraftDirty                     V3 2차: 초기 snapshot vs 현재 draft 비교 (mapped_questions sort 후)
//   - filterQuestionsBySearch          V3 2차: picker 검색 (qid + title case-insensitive)
//
// 모든 함수는 pure function. 외부 dependency / 비결정성 없음.
//
// backend schema 참조 (분석 결과, 외부 source not allowed in code):
//   PatchEvalCriteriaMappingRequest 8 필드:
//   session_id, criteria_name, scope, mapped_questions,
//   mapping_type, confidence, reason, weight

// ─── 상수 ────────────────────────────────────────────────────────────

export const SCOPE_VALUES = ['question', 'section', 'document']
export const MAPPING_TYPE_VALUES = ['direct', 'indirect', 'context']

// PATCH 허용 필드 — backend Pydantic schema 권위 source
const PATCH_ALLOWED_FIELDS = [
  'session_id', 'criteria_name', 'scope', 'mapped_questions',
  'mapping_type', 'confidence', 'reason', 'weight',
]

// KNOWN slug 매핑 (정부지원사업 자주 사용 평가기준 9종)
const KNOWN_SLUG = {
  '기술성': 'tech',
  '사업성': 'biz',
  '수행역량': 'cap',
  '시장성': 'market',
  '혁신성': 'innov',
  '환경친화성': 'eco',
  '지속가능성': 'sustain',
  '고용창출': 'jobs',
  '지역기여': 'local',
}

// ─── 1. nameToSlug ──────────────────────────────────────────────────

/**
 * criteriaName → slug.
 * KNOWN 9종 → 미리 매핑된 영문 slug
 * 미정의 이름 → deterministic hash 'h' + 7자
 *
 * 결정적 보장: 같은 input → 항상 같은 output.
 */
export function nameToSlug(criteriaName) {
  if (!criteriaName || typeof criteriaName !== 'string') return 'h0000000'
  const normalized = criteriaName.trim()
  if (KNOWN_SLUG[normalized]) return KNOWN_SLUG[normalized]
  // 결정적 hash (djb2 변형, 동기)
  let hash = 5381
  for (let i = 0; i < normalized.length; i++) {
    hash = ((hash << 5) + hash) + normalized.charCodeAt(i)
    hash = hash & 0xffffffff   // 32-bit
  }
  const unsigned = (hash >>> 0).toString(16).padStart(8, '0').slice(0, 7)
  return 'h' + unsigned
}

// ─── 2. generateCriteriaId ──────────────────────────────────────────

/**
 * session-scoped criteria_id 생성.
 * 패턴: crit_{sessionId 앞 8자}_{slug}
 * 같은 sessionId + 같은 criteriaName → 항상 같은 id (결정적).
 */
export function generateCriteriaId({ sessionId, criteriaName }) {
  if (!sessionId || !criteriaName) return null
  const shortSession = String(sessionId).slice(0, 8)
  const slug = nameToSlug(criteriaName)
  return `crit_${shortSession}_${slug}`
}

// ─── 3. normalizeEvalCriteriaMappingItem ────────────────────────────

/**
 * 단일 item normalize.
 * - mapped_questions를 validQuestionIds 기준 filter
 * - invalid qid는 제거 + console.warn
 * - 외 필드는 그대로 유지
 */
export function normalizeEvalCriteriaMappingItem({ item, validQuestionIds }) {
  if (!item) return item
  if (!Array.isArray(validQuestionIds) || validQuestionIds.length === 0) {
    // validQuestionIds 빈 경우 — race condition 가능, filter 안 함
    return { ...item, mapped_questions: item.mapped_questions || [] }
  }
  const validSet = new Set(validQuestionIds)
  const original = item.mapped_questions || []
  const filtered = []
  const invalid = []
  for (const qid of original) {
    if (validSet.has(qid)) filtered.push(qid)
    else invalid.push(qid)
  }
  if (invalid.length > 0) {
    console.warn('[EVAL_MAPPING_INVALID_QID_FILTERED]', {
      criteria_id: item.criteria_id,
      criteria_name: item.criteria_name,
      invalidIds: invalid,
    })
  }
  return { ...item, mapped_questions: filtered }
}

// ─── 4. mergeEvalCriteriaMappings ────────────────────────────────────

/**
 * base (AI 자동 mapping) + overlay (backend GET 사용자 편집) merge.
 *
 * dedup 매칭 키 우선순위:
 *   1. criteria_id 정확 일치
 *   2. normalize(criteria_name) 일치
 *   3. 둘 다 다르면 별도 항목으로 보존
 *
 * 모든 결과 item은 normalize 적용 (invalid qid filter).
 */
export function mergeEvalCriteriaMappings({ baseItems = [], overlayItems = [], validQuestionIds = [] }) {
  const normalizeName = (n) => String(n || '').trim().replace(/\s+/g, ' ').toLowerCase()

  // overlay 색인
  const overlayById = new Map()
  const overlayByName = new Map()
  for (const o of overlayItems) {
    if (o.criteria_id) overlayById.set(o.criteria_id, o)
    if (o.criteria_name) overlayByName.set(normalizeName(o.criteria_name), o)
  }

  const usedOverlayIds = new Set()
  const merged = []

  // base 순회 → overlay 매칭 시 user 우선
  for (const b of baseItems) {
    let matched = null
    if (b.criteria_id && overlayById.has(b.criteria_id)) {
      matched = overlayById.get(b.criteria_id)
    } else if (b.criteria_name && overlayByName.has(normalizeName(b.criteria_name))) {
      matched = overlayByName.get(normalizeName(b.criteria_name))
    }
    if (matched) {
      usedOverlayIds.add(matched.criteria_id)
      merged.push(normalizeEvalCriteriaMappingItem({ item: matched, validQuestionIds }))
    } else {
      merged.push(normalizeEvalCriteriaMappingItem({ item: b, validQuestionIds }))
    }
  }

  // overlay 중 base와 매칭 안 된 항목 추가 (backend에만 존재하는 사용자 편집)
  for (const o of overlayItems) {
    if (usedOverlayIds.has(o.criteria_id)) continue
    merged.push(normalizeEvalCriteriaMappingItem({ item: o, validQuestionIds }))
  }

  return merged
}

// ─── 5. buildEvalCriteriaPatchPayload ────────────────────────────────

/**
 * PATCH /eval-criteria-mappings/{id} payload 빌드.
 * - backend Pydantic schema 8 필드만 (allowlist)
 * - mapped_questions는 validQuestionIds 기준 filter (invalid 제외 보장)
 * - draft 안의 undefined / null 필드는 제외 (부분 갱신)
 */
export function buildEvalCriteriaPatchPayload({ sessionId, draft, validQuestionIds = [] }) {
  if (!sessionId) throw new Error('sessionId required')
  const payload = { session_id: sessionId }
  if (!draft || typeof draft !== 'object') return payload

  for (const key of PATCH_ALLOWED_FIELDS) {
    if (key === 'session_id') continue
    const v = draft[key]
    if (v === undefined || v === null) continue
    if (key === 'mapped_questions') {
      if (!Array.isArray(v)) continue
      if (validQuestionIds.length === 0) {
        // race: validQuestionIds 비어있으면 그대로 (filter 안 함)
        payload[key] = [...v]
      } else {
        const validSet = new Set(validQuestionIds)
        payload[key] = v.filter(qid => validSet.has(qid))
      }
    } else {
      payload[key] = v
    }
  }
  return payload
}

// ─── 6. validateEvalCriteriaDraft ────────────────────────────────────

/**
 * 저장 직전 draft validation.
 *
 * 반환: { blockers: [...], warnings: [...] }
 *   - blockers: 저장 차단 (UI: validation 메시지 + 차단)
 *   - warnings: 저장 허용 (UI: 경고 표시 후 저장 가능)
 *
 * 사용자 추가 조건:
 *   - validQuestionIds 빈/로딩 중 + scope=question → 차단
 *   - scope=section + mapped=0 → 경고만
 *   - scope=document + mapped=0 → OK
 *   - scope=question + mapped=0 → 차단
 */
export function validateEvalCriteriaDraft({ draft, validQuestionIds = [] }) {
  const blockers = []
  const warnings = []
  if (!draft || typeof draft !== 'object') {
    blockers.push({ field: 'draft', message: 'draft is required' })
    return { blockers, warnings }
  }

  const { scope, mapping_type, mapped_questions, reason, confidence } = draft

  // scope enum
  if (scope === undefined || scope === null) {
    blockers.push({ field: 'scope', message: 'scope is required' })
  } else if (!SCOPE_VALUES.includes(scope)) {
    blockers.push({ field: 'scope', message: `invalid scope: ${scope}` })
  }

  // mapping_type enum
  if (mapping_type === undefined || mapping_type === null) {
    blockers.push({ field: 'mapping_type', message: 'mapping_type is required' })
  } else if (!MAPPING_TYPE_VALUES.includes(mapping_type)) {
    blockers.push({ field: 'mapping_type', message: `invalid mapping_type: ${mapping_type}` })
  }

  // reason 필수
  if (!reason || String(reason).trim().length === 0) {
    blockers.push({ field: 'reason', message: '수정 사유 (reason) 필수' })
  }

  // mapped_questions
  const mappedArr = Array.isArray(mapped_questions) ? mapped_questions : []
  const validSet = new Set(validQuestionIds)
  const hasValidQids = Array.isArray(validQuestionIds) && validQuestionIds.length > 0

  // FormSchema race: validQuestionIds 빈/로딩 중 + scope=question → 차단
  if (scope === 'question' && !hasValidQids) {
    blockers.push({
      field: 'mapped_questions',
      message: '양식 분석 진행 중입니다. 제출양식 분석이 완료되면 문항 선택이 가능합니다.',
    })
  } else if (hasValidQids) {
    // invalid qid 차단
    const invalid = mappedArr.filter(qid => !validSet.has(qid))
    if (invalid.length > 0) {
      blockers.push({
        field: 'mapped_questions',
        message: `유효하지 않은 문항 ID: ${invalid.join(', ')}`,
      })
    }

    // scope별 mapped=0 정책
    if (mappedArr.length === 0) {
      if (scope === 'question') {
        blockers.push({
          field: 'mapped_questions',
          message: 'question scope에서는 최소 1개 문항을 선택해야 합니다.',
        })
      } else if (scope === 'section') {
        warnings.push({
          field: 'mapped_questions',
          message: 'section scope이지만 매핑 문항이 없습니다.',
        })
      }
      // scope=document + mapped=0은 OK (v5 정책 그대로)
    }
  }

  // confidence 경고 (read-only이지만 backend 값 검증 차원)
  if (typeof confidence === 'number') {
    if (confidence < 0 || confidence > 1) {
      blockers.push({ field: 'confidence', message: `confidence는 0.0~1.0 범위여야 합니다: ${confidence}` })
    } else if (confidence < 0.7) {
      warnings.push({ field: 'confidence', message: `confidence < 0.70 (${confidence})` })
    }
  }

  return { blockers, warnings }
}

// ─── 7. isDraftDirty (V3 2차) ────────────────────────────────────────

/**
 * 초기 snapshot vs 현재 draft 비교.
 * mapped_questions는 sort 후 비교 (배열 순서 무시).
 * scope / mapping_type / reason는 strict equality.
 */
export function isDraftDirty({ initial, current }) {
  if (!initial || !current) return false
  if ((current.scope || '') !== (initial.scope || '')) return true
  if ((current.mapping_type || '') !== (initial.mapping_type || '')) return true
  if ((current.reason || '') !== (initial.reason || '')) return true
  const a = [...(current.mapped_questions || [])].sort()
  const b = [...(initial.mapped_questions || [])].sort()
  if (a.length !== b.length) return true
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return true
  return false
}

// ─── 8. filterQuestionsBySearch (V3 2차) ────────────────────────────

/**
 * picker 검색 — question_id 또는 title 부분 일치 (case-insensitive).
 * section 그룹 보존 (filtered questions, hidden flag).
 *
 * sections: [{ id, title, questions: [{id, title, ...}] }]
 * 반환:     [{ id, title, allQuestions, questions(filtered), hidden }]
 */
export function filterQuestionsBySearch({ sections = [], search = '' }) {
  const q = String(search || '').trim().toLowerCase()
  return sections.map(sec => {
    const allQs = (sec.questions || []).map(qq => ({
      id: qq.id,
      title: qq.title || qq.name || qq.id,
      char_limit: qq.char_limit,
    }))
    const filtered = q
      ? allQs.filter(qq =>
          String(qq.id).toLowerCase().includes(q) ||
          String(qq.title).toLowerCase().includes(q)
        )
      : allQs
    return {
      id: sec.id,
      title: sec.title || sec.name || sec.id,
      allQuestions: allQs,
      questions: filtered,
      hidden: !!q && filtered.length === 0,
    }
  })
}
