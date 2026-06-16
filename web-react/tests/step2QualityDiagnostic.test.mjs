// AJIN BizAI v0.2.1 QG-1 — Step2QualityDiagnostic unit tests

import { describe, it, expect } from 'vitest'
import {
  computeStep2QualityMetrics,
  detectStep2RiskSignals,
  getRiskBadgeMeta,
} from '../src/lib/step2QualityDiagnostic.js'

// 공통 fixture
const fullForm = {
  sections: [
    {
      id: 'I',
      title: 'I',
      questions: [
        { id: 'I-1', status: 'ok', source_page: 3 },
        { id: 'I-2', status: 'weak', source_page: 4 },
        { id: 'I-3', status: 'missing', source_page: null },
      ],
    },
    {
      id: 'III',
      title: 'III',
      questions: [
        { id: 'III-1', status: 'ok', source_page: 8 },
        { id: 'III-T1', status: 'ok', source_page: '' },  // 빈 문자열 = 누락
      ],
    },
  ],
}

const fullNotice = {
  target: '중소기업',
  benefit: '최대 2억원',
  deadline: '2026-06-15',
  required_documents: ['A', 'B', 'C', 'D'],
  evaluation_criteria: [{ name: '기술성', weight: 40 }],
}

const fullEvalMapping = {
  mappings: [
    { criteria_id: 'crit_tech', criteria_name: '기술성', weight: 40,
      mapped_questions: ['I-1', 'III-1'] },
    { criteria_id: 'crit_biz', criteria_name: '사업성', weight: 30,
      mapped_questions: ['I-2'] },
    { criteria_id: 'crit_cap', criteria_name: '수행역량', weight: 30,
      mapped_questions: ['III-T1'] },
  ],
}

const validIds = ['I-1', 'I-2', 'I-3', 'III-1', 'III-T1']

// ─── 1. computeStep2QualityMetrics ─────────────────────────────

describe('computeStep2QualityMetrics', () => {
  it('1. 모든 데이터 정상 → 주요 지표 정확', () => {
    const m = computeStep2QualityMetrics({
      noticeApiResp: fullNotice,
      formData: fullForm,
      evalCriteriaMapping: fullEvalMapping,
      validQuestionIds: validIds,
    })
    expect(m.questionCount).toBe(5)
    expect(m.okCount).toBe(3)
    expect(m.weakCount).toBe(1)
    expect(m.missingCount).toBe(1)
    expect(m.evalCriteriaCount).toBe(3)
    expect(m.evalCriteriaWeightSum).toBe(100)
    expect(m.requiredDocsCount).toBe(4)
    expect(m.invalidQuestionIdCount).toBe(0)
    expect(m.duplicateQuestionIdCount).toBe(0)
    expect(m.hasData).toBe(true)
    expect(m.isLoading).toBe(false)
  })

  it('2. noticeApiResp null → 공고 관련 지표 데이터 없음 처리', () => {
    const m = computeStep2QualityMetrics({
      noticeApiResp: null,
      formData: fullForm,
      evalCriteriaMapping: fullEvalMapping,
      validQuestionIds: validIds,
    })
    expect(m.requiredDocsCount).toBe(0)
    expect(m.hasData).toBe(true)  // formData 있음
    expect(m.isLoading).toBe(false)
  })

  it('3. evalCriteriaMapping 빈 → noticeApiResp.evaluation_criteria fallback 사용', () => {
    // notice_analyst만 끝나고 evalCriteriaMapping이 아직 없을 때 false-positive 방지
    const m = computeStep2QualityMetrics({
      noticeApiResp: fullNotice,
      formData: fullForm,
      evalCriteriaMapping: { mappings: [] },
      validQuestionIds: validIds,
    })
    expect(m.evalCriteriaCount).toBe(fullNotice.evaluation_criteria.length)
    expect(m.evalCriteriaWeightSum).toBe(40)
    expect(m.invalidQuestionIdCount).toBe(0)  // fallback의 mapped_questions은 빈 배열
  })

  it('3b. evalCriteriaMapping + noticeApiResp 둘 다 비어있음 → 평가기준 수 0', () => {
    const m = computeStep2QualityMetrics({
      noticeApiResp: { ...fullNotice, evaluation_criteria: [] },
      formData: fullForm,
      evalCriteriaMapping: { mappings: [] },
      validQuestionIds: validIds,
    })
    expect(m.evalCriteriaCount).toBe(0)
    expect(m.evalCriteriaWeightSum).toBe(0)
  })

  it('4. formData 없음 → 제출양식 데이터 없음', () => {
    const m = computeStep2QualityMetrics({
      noticeApiResp: fullNotice,
      formData: null,
      evalCriteriaMapping: fullEvalMapping,
      validQuestionIds: [],
    })
    expect(m.questionCount).toBe(0)
    expect(m.okCount + m.weakCount + m.missingCount).toBe(0)
    expect(m.sufficiencyPercent).toBeNull()
    expect(m.hasData).toBe(true)  // noticeApiResp 있음
  })

  it('5. 추출 문항 0개 → questionCount 0', () => {
    const m = computeStep2QualityMetrics({
      formData: { sections: [{ id: 's', title: 's', questions: [] }] },
    })
    expect(m.questionCount).toBe(0)
  })

  it('6. sufficiency 공식: ok=3, weak=2, missing=5 → 40', () => {
    const form = {
      sections: [{ id: 's', title: 's', questions: [
        ...Array.from({ length: 3 }, (_, i) => ({ id: `ok-${i}`, status: 'ok' })),
        ...Array.from({ length: 2 }, (_, i) => ({ id: `weak-${i}`, status: 'weak' })),
        ...Array.from({ length: 5 }, (_, i) => ({ id: `miss-${i}`, status: 'missing' })),
      ] }],
    }
    const m = computeStep2QualityMetrics({ formData: form })
    expect(m.okCount).toBe(3)
    expect(m.weakCount).toBe(2)
    expect(m.missingCount).toBe(5)
    expect(m.sufficiencyPercent).toBe(40)  // (3 + 2*0.5)/10 = 40
  })

  it('7. sufficiency total=0 → null (데이터 없음)', () => {
    const m = computeStep2QualityMetrics({ formData: null })
    expect(m.sufficiencyPercent).toBeNull()
  })

  it('8. mapped_questions에 invalid qid 2개 → invalidQuestionIdCount=2', () => {
    const m = computeStep2QualityMetrics({
      formData: fullForm,
      evalCriteriaMapping: {
        mappings: [
          { criteria_id: 'c1', criteria_name: 'X', weight: 0,
            mapped_questions: ['I-1', 'UNKNOWN-1', 'III-1', 'UNKNOWN-2'] },
        ],
      },
      validQuestionIds: validIds,
    })
    expect(m.invalidQuestionIdCount).toBe(2)
  })

  it('9. source_page 누락 → sourcePageMissingCount 정확 (null + 빈 문자열)', () => {
    const m = computeStep2QualityMetrics({ formData: fullForm })
    // fullForm: I-3 (null) + III-T1 ('') = 2개
    expect(m.sourcePageMissingCount).toBe(2)
  })

  it('10. question_id 중복 → duplicateQuestionIdCount 정확', () => {
    const dupForm = {
      sections: [
        { id: 's1', title: 's1', questions: [{ id: 'X-1' }, { id: 'X-2' }] },
        { id: 's2', title: 's2', questions: [{ id: 'X-1' }, { id: 'X-3' }] },  // X-1 중복
      ],
    }
    const m = computeStep2QualityMetrics({ formData: dupForm })
    expect(m.questionCount).toBe(4)
    expect(m.duplicateQuestionIdCount).toBe(1)  // X-1이 1번 중복
  })

  it('isLoading: 양 데이터 모두 없으면 true', () => {
    const m = computeStep2QualityMetrics({ noticeApiResp: null, formData: null })
    expect(m.hasData).toBe(false)
    expect(m.isLoading).toBe(true)
  })

  it('evalCriteria dedup: 같은 criteria_name → 1개로 카운트', () => {
    const m = computeStep2QualityMetrics({
      evalCriteriaMapping: {
        mappings: [
          { criteria_id: 'crit_ai_market', criteria_name: '시장성', weight: 30, mapped_questions: [] },
          { criteria_id: 'crit_user_market', criteria_name: '시장성', weight: 30, mapped_questions: [] },
        ],
      },
    })
    expect(m.evalCriteriaCount).toBe(1)
    expect(m.evalCriteriaWeightSum).toBe(30)
  })
})

// ─── 2. detectStep2RiskSignals ─────────────────────────────────

describe('detectStep2RiskSignals', () => {
  it('11. 마감일 없음 → "마감일 정보 없음"', () => {
    const m = computeStep2QualityMetrics({
      noticeApiResp: { target: '중소기업', deadline: null, required_documents: ['a'] },
      formData: fullForm,
      evalCriteriaMapping: fullEvalMapping,
      validQuestionIds: validIds,
    })
    const r = detectStep2RiskSignals(m)
    expect(r.signals).toContain('마감일 정보 없음')
  })

  it('12. 평가기준 0개 (mapping + notice 둘 다 비어있음) → "평가기준 추출 안 됨"', () => {
    const m = computeStep2QualityMetrics({
      noticeApiResp: { ...fullNotice, evaluation_criteria: [] },
      formData: fullForm,
      evalCriteriaMapping: { mappings: [] },
      validQuestionIds: validIds,
    })
    const r = detectStep2RiskSignals(m)
    expect(r.signals).toContain('평가기준 추출 안 됨')
  })

  it('13. 모두 정상 → 위험 신호 빈 배열', () => {
    const m = computeStep2QualityMetrics({
      noticeApiResp: fullNotice,
      formData: fullForm,
      evalCriteriaMapping: fullEvalMapping,
      validQuestionIds: validIds,
    })
    const r = detectStep2RiskSignals(m)
    // fullForm에는 source_page 누락 2개 (I-3 null + III-T1 '')
    // 정상이라 평가기준/마감/필수서류는 OK지만 source_page 누락은 위험으로 잡힘
    expect(r.signals).toEqual(['source_page 누락 2개'])
  })

  it('지원대상 빈 문자열 → "지원대상 정보 없음"', () => {
    const m = computeStep2QualityMetrics({
      noticeApiResp: { target: '   ', deadline: '2026-06-15', required_documents: ['a'] },
      formData: fullForm,
      evalCriteriaMapping: fullEvalMapping,
      validQuestionIds: validIds,
    })
    const r = detectStep2RiskSignals(m)
    expect(r.signals).toContain('지원대상 정보 없음')
  })

  it('필수서류 == null → "필수서류 정보 없음" (빈 배열은 다른 케이스)', () => {
    const m1 = computeStep2QualityMetrics({
      noticeApiResp: { target: 't', deadline: 'd' },  // required_documents 미정의
      formData: fullForm,
      evalCriteriaMapping: fullEvalMapping,
      validQuestionIds: validIds,
    })
    expect(detectStep2RiskSignals(m1).signals).toContain('필수서류 정보 없음')

    const m2 = computeStep2QualityMetrics({
      noticeApiResp: { target: 't', deadline: 'd', required_documents: [] },  // 빈 배열
      formData: fullForm,
      evalCriteriaMapping: fullEvalMapping,
      validQuestionIds: validIds,
    })
    expect(detectStep2RiskSignals(m2).signals).not.toContain('필수서류 정보 없음')
  })

  it('최대 3개 표시 + "외 N개"', () => {
    // 6개 위험 발생
    const m = computeStep2QualityMetrics({
      noticeApiResp: { /* target/deadline/required_documents 모두 누락 */ },
      formData: { sections: [{ id: 's', title: 's', questions: [] }] },
      evalCriteriaMapping: { mappings: [] },
      validQuestionIds: [],
    })
    const r = detectStep2RiskSignals(m)
    expect(r.count).toBeGreaterThanOrEqual(5)
    expect(r.displayedSignals.length).toBe(3)
    expect(r.hiddenCount).toBe(r.count - 3)
  })

  it('null metrics 안전 처리', () => {
    const r = detectStep2RiskSignals(null)
    expect(r.signals).toEqual([])
    expect(r.count).toBe(0)
  })
})

// ─── 3. getRiskBadgeMeta ──────────────────────────────────────

describe('getRiskBadgeMeta', () => {
  it('데이터 없음', () => {
    const b = getRiskBadgeMeta({ riskCount: 0, isLoading: false, hasData: false })
    expect(b.status).toBe('no_data')
    expect(b.label).toBe('데이터 없음')
    expect(b.color).toBe('slate')
  })

  it('분석 중', () => {
    const b = getRiskBadgeMeta({ riskCount: 0, isLoading: true, hasData: false })
    expect(b.status).toBe('analyzing')
    expect(b.label).toBe('분석 중')
    expect(b.color).toBe('amber')
  })

  it('위험 신호 없음 → emerald', () => {
    const b = getRiskBadgeMeta({ riskCount: 0, isLoading: false, hasData: true })
    expect(b.status).toBe('ok')
    expect(b.label).toBe('위험 신호 없음')
    expect(b.color).toBe('emerald')
  })

  it('위험 1~2개 → amber', () => {
    expect(getRiskBadgeMeta({ riskCount: 1, hasData: true }).color).toBe('amber')
    expect(getRiskBadgeMeta({ riskCount: 2, hasData: true }).color).toBe('amber')
  })

  it('위험 3개 이상 → rose', () => {
    expect(getRiskBadgeMeta({ riskCount: 3, hasData: true }).color).toBe('rose')
    expect(getRiskBadgeMeta({ riskCount: 7, hasData: true }).label).toBe('위험 신호 7개')
  })
})
