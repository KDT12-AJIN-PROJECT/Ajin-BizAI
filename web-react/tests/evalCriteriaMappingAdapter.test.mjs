// AJIN BizAI v0.2.1 V3 — evalCriteriaMappingAdapter unit tests
//
// vitest, pure function 검증.
// 4 그룹: nameToSlug+generateCriteriaId / normalize / merge / validation+payload

import { describe, it, expect, vi } from 'vitest'
import {
  nameToSlug,
  generateCriteriaId,
  normalizeEvalCriteriaMappingItem,
  mergeEvalCriteriaMappings,
  buildEvalCriteriaPatchPayload,
  validateEvalCriteriaDraft,
  isDraftDirty,
  filterQuestionsBySearch,
  SCOPE_VALUES,
  MAPPING_TYPE_VALUES,
} from '../src/lib/evalCriteriaMappingAdapter.js'

// ─── 1. nameToSlug + generateCriteriaId ─────────────────────────────

describe('nameToSlug', () => {
  it('KNOWN 9종: 기술성 → tech', () => {
    expect(nameToSlug('기술성')).toBe('tech')
    expect(nameToSlug('사업성')).toBe('biz')
    expect(nameToSlug('수행역량')).toBe('cap')
    expect(nameToSlug('시장성')).toBe('market')
    expect(nameToSlug('혁신성')).toBe('innov')
    expect(nameToSlug('환경친화성')).toBe('eco')
    expect(nameToSlug('지속가능성')).toBe('sustain')
    expect(nameToSlug('고용창출')).toBe('jobs')
    expect(nameToSlug('지역기여')).toBe('local')
  })

  it('미정의 이름: hash 8자 (h prefix)', () => {
    const slug = nameToSlug('새로운평가기준')
    expect(slug).toMatch(/^h[0-9a-f]{7}$/)
  })

  it('결정성: 같은 input → 같은 output', () => {
    const name = '미정의평가기준A'
    expect(nameToSlug(name)).toBe(nameToSlug(name))
    expect(nameToSlug('기술성')).toBe(nameToSlug('기술성'))
  })

  it('빈 input 안전 처리', () => {
    expect(nameToSlug(null)).toBe('h0000000')
    expect(nameToSlug('')).toBe('h0000000')
    expect(nameToSlug(undefined)).toBe('h0000000')
  })

  it('공백 정리 후 KNOWN 매칭', () => {
    expect(nameToSlug('  기술성  ')).toBe('tech')
  })
})

describe('generateCriteriaId', () => {
  it('패턴: crit_{sessionShort}_{slug}', () => {
    const id = generateCriteriaId({ sessionId: 'abcdef1234567890', criteriaName: '기술성' })
    expect(id).toBe('crit_abcdef12_tech')
  })

  it('결정성: 같은 input → 같은 id', () => {
    const a = generateCriteriaId({ sessionId: 'session001', criteriaName: '사업성' })
    const b = generateCriteriaId({ sessionId: 'session001', criteriaName: '사업성' })
    expect(a).toBe(b)
  })

  it('미정의 이름도 결정적 id', () => {
    const a = generateCriteriaId({ sessionId: 'sess0001', criteriaName: '신평가기준X' })
    const b = generateCriteriaId({ sessionId: 'sess0001', criteriaName: '신평가기준X' })
    expect(a).toBe(b)
    expect(a).toMatch(/^crit_sess0001_h[0-9a-f]{7}$/)
  })

  it('null safety', () => {
    expect(generateCriteriaId({ sessionId: null, criteriaName: '기술성' })).toBeNull()
    expect(generateCriteriaId({ sessionId: 'x', criteriaName: null })).toBeNull()
  })
})

// ─── 2. normalize ──────────────────────────────────────────────────

describe('normalizeEvalCriteriaMappingItem', () => {
  it('invalid qid filter + console.warn', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const item = {
      criteria_id: 'c1',
      criteria_name: '시장성',
      mapped_questions: ['I-1', 'X-99', 'III-T1', 'Z-0'],
    }
    const out = normalizeEvalCriteriaMappingItem({
      item,
      validQuestionIds: ['I-1', 'I-2', 'III-T1'],
    })
    expect(out.mapped_questions).toEqual(['I-1', 'III-T1'])
    expect(warn).toHaveBeenCalledWith(
      '[EVAL_MAPPING_INVALID_QID_FILTERED]',
      expect.objectContaining({ invalidIds: ['X-99', 'Z-0'] })
    )
    warn.mockRestore()
  })

  it('validQuestionIds 빈 → filter 안 함 (race 안전)', () => {
    const item = { criteria_id: 'c1', mapped_questions: ['ANY-1', 'ANY-2'] }
    const out = normalizeEvalCriteriaMappingItem({ item, validQuestionIds: [] })
    expect(out.mapped_questions).toEqual(['ANY-1', 'ANY-2'])
  })

  it('mapped_questions 없으면 빈 배열', () => {
    const out = normalizeEvalCriteriaMappingItem({
      item: { criteria_id: 'c1' },
      validQuestionIds: ['I-1'],
    })
    expect(out.mapped_questions).toEqual([])
  })
})

// ─── 3. merge ──────────────────────────────────────────────────────

describe('mergeEvalCriteriaMappings', () => {
  it('criteria_id 일치: overlay (user) 우선', () => {
    const base = [{ criteria_id: 'c1', criteria_name: '기술성', mapped_by: 'ai', mapped_questions: ['I-1'] }]
    const overlay = [{ criteria_id: 'c1', criteria_name: '기술성', mapped_by: 'user', mapped_questions: ['I-1', 'III-1'] }]
    const out = mergeEvalCriteriaMappings({
      baseItems: base, overlayItems: overlay, validQuestionIds: ['I-1', 'III-1'],
    })
    expect(out).toHaveLength(1)
    expect(out[0].mapped_by).toBe('user')
    expect(out[0].mapped_questions).toEqual(['I-1', 'III-1'])
  })

  it('criteria_id 다르지만 name 일치: overlay 우선 (name fallback dedup)', () => {
    const base = [{ criteria_id: 'crit_market', criteria_name: '시장성', mapped_by: 'ai' }]
    const overlay = [{ criteria_id: 'crit_abc123_market', criteria_name: '시장성', mapped_by: 'user', mapped_questions: ['I-2'] }]
    const out = mergeEvalCriteriaMappings({
      baseItems: base, overlayItems: overlay, validQuestionIds: ['I-2'],
    })
    expect(out).toHaveLength(1)  // 중복 카드 없음
    expect(out[0].mapped_by).toBe('user')
    expect(out[0].criteria_id).toBe('crit_abc123_market')
  })

  it('name normalize: 공백/대소문자 무시', () => {
    const base = [{ criteria_id: 'b1', criteria_name: ' 기술성 ', mapped_by: 'ai' }]
    const overlay = [{ criteria_id: 'o1', criteria_name: '기술성', mapped_by: 'user', mapped_questions: ['I-1'] }]
    const out = mergeEvalCriteriaMappings({
      baseItems: base, overlayItems: overlay, validQuestionIds: ['I-1'],
    })
    expect(out).toHaveLength(1)
    expect(out[0].mapped_by).toBe('user')
  })

  it('backend에만 있는 item: 추가 표시', () => {
    const base = [{ criteria_id: 'b1', criteria_name: '기술성', mapped_by: 'ai' }]
    const overlay = [{ criteria_id: 'b1', criteria_name: '기술성', mapped_by: 'user' },
                     { criteria_id: 'b2', criteria_name: '특별기준', mapped_by: 'user' }]
    const out = mergeEvalCriteriaMappings({ baseItems: base, overlayItems: overlay, validQuestionIds: [] })
    expect(out).toHaveLength(2)
    expect(out.map(o => o.criteria_name).sort()).toEqual(['기술성', '특별기준'])
  })

  it('빈 overlay: base 그대로', () => {
    const base = [{ criteria_id: 'b1', criteria_name: '기술성' }]
    const out = mergeEvalCriteriaMappings({ baseItems: base, overlayItems: [], validQuestionIds: [] })
    expect(out).toHaveLength(1)
    expect(out[0].criteria_name).toBe('기술성')
  })

  it('전체 base 대체 안 함 (overlay만으로 base 무효화 X)', () => {
    const base = [
      { criteria_id: 'b1', criteria_name: '기술성', mapped_by: 'ai' },
      { criteria_id: 'b2', criteria_name: '사업성', mapped_by: 'ai' },
      { criteria_id: 'b3', criteria_name: '수행역량', mapped_by: 'ai' },
    ]
    const overlay = [{ criteria_id: 'b1', criteria_name: '기술성', mapped_by: 'user' }]
    const out = mergeEvalCriteriaMappings({ baseItems: base, overlayItems: overlay, validQuestionIds: [] })
    expect(out).toHaveLength(3)  // base 3개 모두 보존
  })
})

// ─── 4. validation + payload ───────────────────────────────────────

describe('validateEvalCriteriaDraft', () => {
  const validIds = ['I-1', 'I-2', 'III-1', 'III-T1']

  it('valid question scope', () => {
    const v = validateEvalCriteriaDraft({
      draft: { scope: 'question', mapping_type: 'direct', mapped_questions: ['I-1'], reason: '사유' },
      validQuestionIds: validIds,
    })
    expect(v.blockers).toEqual([])
  })

  it('valid section scope (mapped > 0)', () => {
    const v = validateEvalCriteriaDraft({
      draft: { scope: 'section', mapping_type: 'direct', mapped_questions: ['I-1', 'I-2'], reason: '사유' },
      validQuestionIds: validIds,
    })
    expect(v.blockers).toEqual([])
  })

  it('section + mapped=0: 경고만 (저장 가능)', () => {
    const v = validateEvalCriteriaDraft({
      draft: { scope: 'section', mapping_type: 'direct', mapped_questions: [], reason: '사유' },
      validQuestionIds: validIds,
    })
    expect(v.blockers).toEqual([])
    expect(v.warnings).toHaveLength(1)
    expect(v.warnings[0].field).toBe('mapped_questions')
  })

  it('document + mapped=0: OK (v5 정책)', () => {
    const v = validateEvalCriteriaDraft({
      draft: { scope: 'document', mapping_type: 'direct', mapped_questions: [], reason: '사유' },
      validQuestionIds: validIds,
    })
    expect(v.blockers).toEqual([])
  })

  it('question + mapped=0: 차단', () => {
    const v = validateEvalCriteriaDraft({
      draft: { scope: 'question', mapping_type: 'direct', mapped_questions: [], reason: '사유' },
      validQuestionIds: validIds,
    })
    expect(v.blockers.some(b => b.field === 'mapped_questions')).toBe(true)
  })

  it('FormSchema race (validIds 빈) + scope=question: 차단', () => {
    const v = validateEvalCriteriaDraft({
      draft: { scope: 'question', mapping_type: 'direct', mapped_questions: ['I-1'], reason: '사유' },
      validQuestionIds: [],
    })
    expect(v.blockers.some(b => b.message.includes('양식 분석 진행 중'))).toBe(true)
  })

  it('invalid scope: 차단', () => {
    const v = validateEvalCriteriaDraft({
      draft: { scope: 'invalid', mapping_type: 'direct', mapped_questions: [], reason: '사유' },
      validQuestionIds: validIds,
    })
    expect(v.blockers.some(b => b.field === 'scope')).toBe(true)
  })

  it('invalid mapping_type: 차단', () => {
    const v = validateEvalCriteriaDraft({
      draft: { scope: 'section', mapping_type: 'foo', mapped_questions: [], reason: '사유' },
      validQuestionIds: validIds,
    })
    expect(v.blockers.some(b => b.field === 'mapping_type')).toBe(true)
  })

  it('unknown question_id: 차단', () => {
    const v = validateEvalCriteriaDraft({
      draft: { scope: 'question', mapping_type: 'direct', mapped_questions: ['UNKNOWN-99'], reason: '사유' },
      validQuestionIds: validIds,
    })
    expect(v.blockers.some(b => b.field === 'mapped_questions')).toBe(true)
  })

  it('empty reason: 차단', () => {
    const v = validateEvalCriteriaDraft({
      draft: { scope: 'document', mapping_type: 'direct', mapped_questions: [], reason: '   ' },
      validQuestionIds: validIds,
    })
    expect(v.blockers.some(b => b.field === 'reason')).toBe(true)
  })
})

describe('buildEvalCriteriaPatchPayload', () => {
  it('allowlist: extra field 제거', () => {
    const out = buildEvalCriteriaPatchPayload({
      sessionId: 's1',
      draft: {
        scope: 'question',
        mapping_type: 'direct',
        mapped_questions: ['I-1'],
        reason: '사유',
        // 다음은 모두 schema 밖 → 제거되어야
        source_criteria_id: 'old_id',
        original_mapped_by: 'ai',
        random_extra: 'noise',
      },
      validQuestionIds: ['I-1'],
    })
    expect(Object.keys(out).sort()).toEqual(
      ['mapped_questions', 'mapping_type', 'reason', 'scope', 'session_id']
    )
  })

  it('mapped_questions: invalid qid filter', () => {
    const out = buildEvalCriteriaPatchPayload({
      sessionId: 's1',
      draft: { mapped_questions: ['I-1', 'UNKNOWN', 'III-T1'] },
      validQuestionIds: ['I-1', 'III-T1'],
    })
    expect(out.mapped_questions).toEqual(['I-1', 'III-T1'])
  })

  it('validQuestionIds 빈: filter 안 함 (race 안전)', () => {
    const out = buildEvalCriteriaPatchPayload({
      sessionId: 's1',
      draft: { mapped_questions: ['I-1', 'X-99'] },
      validQuestionIds: [],
    })
    expect(out.mapped_questions).toEqual(['I-1', 'X-99'])
  })

  it('undefined/null 필드 제외 (부분 갱신)', () => {
    const out = buildEvalCriteriaPatchPayload({
      sessionId: 's1',
      draft: { scope: 'section', mapping_type: null, reason: undefined },
      validQuestionIds: [],
    })
    expect(out).toEqual({ session_id: 's1', scope: 'section' })
  })

  it('sessionId 없으면 throw', () => {
    expect(() => buildEvalCriteriaPatchPayload({ sessionId: null, draft: {} })).toThrow()
  })
})

describe('상수 export', () => {
  it('SCOPE_VALUES = 3개', () => {
    expect(SCOPE_VALUES).toEqual(['question', 'section', 'document'])
  })
  it('MAPPING_TYPE_VALUES = 3개', () => {
    expect(MAPPING_TYPE_VALUES).toEqual(['direct', 'indirect', 'context'])
  })
})

// ─── 5. isDraftDirty (V3 2차) ───────────────────────────────────────

describe('isDraftDirty', () => {
  const initial = {
    scope: 'section',
    mapping_type: 'direct',
    mapped_questions: ['I-1', 'III-1'],
    reason: '초기 사유',
  }
  it('동일: dirty=false', () => {
    expect(isDraftDirty({ initial, current: { ...initial } })).toBe(false)
  })
  it('scope 변경: dirty', () => {
    expect(isDraftDirty({ initial, current: { ...initial, scope: 'question' } })).toBe(true)
  })
  it('mapping_type 변경: dirty', () => {
    expect(isDraftDirty({ initial, current: { ...initial, mapping_type: 'context' } })).toBe(true)
  })
  it('reason 변경: dirty', () => {
    expect(isDraftDirty({ initial, current: { ...initial, reason: '새 사유' } })).toBe(true)
  })
  it('mapped_questions 순서만 다름: dirty=false (sort 후 비교)', () => {
    expect(isDraftDirty({ initial, current: { ...initial, mapped_questions: ['III-1', 'I-1'] } })).toBe(false)
  })
  it('mapped_questions 원소 변경: dirty', () => {
    expect(isDraftDirty({ initial, current: { ...initial, mapped_questions: ['I-1', 'III-2'] } })).toBe(true)
  })
  it('mapped_questions 길이 변경: dirty', () => {
    expect(isDraftDirty({ initial, current: { ...initial, mapped_questions: ['I-1'] } })).toBe(true)
  })
  it('null 안전', () => {
    expect(isDraftDirty({ initial: null, current: { scope: 'section' } })).toBe(false)
  })
})

// ─── 6. filterQuestionsBySearch (V3 2차) ────────────────────────────

describe('filterQuestionsBySearch', () => {
  const sections = [
    {
      id: 'sec-I',
      title: 'I. 기업 정보',
      questions: [
        { id: 'I-1', title: '기업 현황' },
        { id: 'I-2', title: '주요 제품/서비스' },
      ],
    },
    {
      id: 'sec-III',
      title: 'III. 사업 추진 계획',
      questions: [
        { id: 'III-1', title: '기술 개발 계획' },
        { id: 'III-T1', title: '추진 일정표' },
      ],
    },
  ]

  it('빈 검색: 모든 question 표시 + hidden=false', () => {
    const out = filterQuestionsBySearch({ sections, search: '' })
    expect(out).toHaveLength(2)
    expect(out[0].questions).toHaveLength(2)
    expect(out[0].hidden).toBe(false)
  })

  it('qid 부분 일치', () => {
    const out = filterQuestionsBySearch({ sections, search: 'III' })
    expect(out[0].hidden).toBe(true)                // I 섹션 hide
    expect(out[1].hidden).toBe(false)
    expect(out[1].questions.map(q => q.id)).toEqual(['III-1', 'III-T1'])
  })

  it('title 부분 일치 (case-insensitive)', () => {
    const out = filterQuestionsBySearch({ sections, search: '기술' })
    expect(out[1].questions.map(q => q.id)).toEqual(['III-1'])  // '기술 개발 계획'
  })

  it('매칭 없음: 모든 section hidden', () => {
    const out = filterQuestionsBySearch({ sections, search: 'ZZZZZ' })
    expect(out.every(s => s.hidden)).toBe(true)
  })

  it('allQuestions 보존 (선택 카운트 용)', () => {
    const out = filterQuestionsBySearch({ sections, search: 'III' })
    expect(out[0].allQuestions).toHaveLength(2)  // hide 됐지만 allQuestions는 보존
  })
})
