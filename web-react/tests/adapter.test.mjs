// Phase 4-H B1-β — frontend adapter 단위 테스트 (vitest)
//
// 사용자 명세 5 단위:
//   1. missingAdapter (adapt/auto/pending/sufficiency)
//   2. reviewAdapter (group/derive/compute/build, scope 분기)
//   3. sessionStatus (statusToStep / resolveSessionStep / active)
//   4. runtimeLog (handleFallback 동작 + DISABLE_FALLBACK)
//   5. form/notice adapter null safety (adaptNoticeFromApi / adaptFormFromApi / applyStatusToForm)
//
// 목표: Phase 4-G adapter 함수 lock-in (회귀 방지).
// 실행: cd web-react && npx vitest run

import { describe, it, expect, vi } from 'vitest'
import {
  SESSION_STATUS, ACTIVE_STATUSES, statusToStep, resolveSessionStep, isActiveStatus,
} from '../src/lib/sessionStatus.js'
import {
  adaptMissingItems, adaptAutoMatchedCards, adaptPendingMatchCards, deriveSufficiency,
  findQuestionMeta, adaptSelectedQuestion,
} from '../src/lib/missingAdapter.js'
import {
  groupDraftStatus, deriveWriteStatus, deriveEvidence, deriveMissing,
  computeCriterionProgress, buildChecklist, computeWriteSummary, computeMaterialsSummary,
  countNeedsRevision,
} from '../src/lib/reviewAdapter.js'
import { logApi, handleFallback, isFallbackBlocked } from '../src/lib/runtimeLog.js'

// ─────────────────────────────────────────────────────────────────────
// 1. sessionStatus
// ─────────────────────────────────────────────────────────────────────
describe('sessionStatus', () => {
  it('statusToStep — 8 enum 매핑', () => {
    expect(statusToStep('created')).toBe(1)
    expect(statusToStep('analyzing')).toBe(2)
    expect(statusToStep('analysis_ready')).toBe(2)
    expect(statusToStep('step2_confirmed')).toBe(3)
    expect(statusToStep('drafting')).toBe(3)
    expect(statusToStep('completed')).toBe(5)
    expect(statusToStep('abandoned')).toBeNull()
    expect(statusToStep('failed')).toBeNull()
  })

  it('ACTIVE_STATUSES — 5 enum', () => {
    expect(ACTIVE_STATUSES).toEqual([
      'created', 'analyzing', 'analysis_ready', 'step2_confirmed', 'drafting'
    ])
  })

  it('isActiveStatus — completed/abandoned 제외', () => {
    expect(isActiveStatus('drafting')).toBe(true)
    expect(isActiveStatus('completed')).toBe(false)
    expect(isActiveStatus('abandoned')).toBe(false)
  })

  it('resolveSessionStep — backend current_step 우선', () => {
    expect(resolveSessionStep({ status: 'drafting', current_step: 3 })).toBe(3)
  })

  it('resolveSessionStep — invalid current_step → status mapping fallback', () => {
    expect(resolveSessionStep({ status: 'drafting', current_step: 99 })).toBe(3)
    expect(resolveSessionStep({ status: 'drafting', current_step: 0 })).toBe(3)
  })

  it('resolveSessionStep — 모두 unknown → 1 (defensive)', () => {
    expect(resolveSessionStep({ status: 'unknown', current_step: null })).toBe(1)
    expect(resolveSessionStep(null)).toBe(1)
  })
})

// ─────────────────────────────────────────────────────────────────────
// 2. missingAdapter
// ─────────────────────────────────────────────────────────────────────
describe('missingAdapter', () => {
  const items = [
    { missing_id: 'm1', question_id: 'I-1', name: 'A', input_type: 'text', status: 'open' },
    { missing_id: 'm2', question_id: 'I-1', name: 'B', input_type: 'file', status: 'resolved' },  // 필터됨
    { missing_id: 'm3', question_id: 'I-1', name: 'C', input_type: 'either', status: 'open' },
    { missing_id: 'm4', question_id: 'II-1', name: 'D', input_type: 'text', status: 'open' },
  ]

  it('adaptMissingItems — selectedQid 필터 + resolved 제외', () => {
    const out = adaptMissingItems(items, 'I-1')
    expect(out).toHaveLength(2)
    expect(out.map(x => x.id)).toEqual(['m1', 'm3'])
  })

  it('adaptMissingItems — input_type 별 actions', () => {
    const out = adaptMissingItems(items, 'I-1')
    expect(out[0].actions).toContain('직접입력')  // text
    expect(out[1].actions).toContain('직접입력')  // either
    expect(out[1].actions).toContain('파일업로드')
  })

  it('adaptMissingItems — null safety', () => {
    expect(adaptMissingItems(null, 'I-1')).toEqual([])
    expect(adaptMissingItems(undefined, 'I-1')).toEqual([])
  })

  const bulkResults = [
    { supplemental_id: 's1', file_name: 'a.pdf', target_question_id: 'I-1', confidence: 0.85, auto_match: true, status: 'analyzed' },
    { supplemental_id: 's2', file_name: 'b.pdf', target_question_id: 'I-2', confidence: 0.65, auto_match: false, status: 'uploaded' },
  ]

  it('adaptAutoMatchedCards — confidence >= 0.70', () => {
    const out = adaptAutoMatchedCards(bulkResults)
    expect(out).toHaveLength(1)
    expect(out[0].supplemental_id).toBe('s1')
    expect(out[0].confidence).toBe(85)
  })

  it('adaptPendingMatchCards — confidence < 0.70', () => {
    const out = adaptPendingMatchCards(bulkResults)
    expect(out).toHaveLength(1)
    expect(out[0].supplemental_id).toBe('s2')
  })

  it('deriveSufficiency — formData 통계', () => {
    const form = { sections: [
      { questions: [{ status: 'ok' }, { status: 'weak' }, { status: 'missing' }] },
    ]}
    expect(deriveSufficiency(form)).toEqual({ ok: 1, weak: 1, missing: 1, total: 3, percent: 50 })
  })

  it('deriveSufficiency — null safety', () => {
    expect(deriveSufficiency(null)).toEqual({ ok: 0, weak: 0, missing: 0, total: 0, percent: 0 })
    expect(deriveSufficiency({})).toEqual({ ok: 0, weak: 0, missing: 0, total: 0, percent: 0 })
  })
})

// ─────────────────────────────────────────────────────────────────────
// 3. reviewAdapter
// ─────────────────────────────────────────────────────────────────────
describe('reviewAdapter — group/derive', () => {
  it('groupDraftStatus — 3 그룹', () => {
    expect(groupDraftStatus('approved')).toBe('approved')
    expect(groupDraftStatus('generated')).toBe('written')
    expect(groupDraftStatus('user_edited')).toBe('written')
    expect(groupDraftStatus('needs_revision')).toBe('written')
    expect(groupDraftStatus('draft')).toBe('unwritten')
    expect(groupDraftStatus('blocked')).toBe('unwritten')
    expect(groupDraftStatus('unknown')).toBe('unwritten')  // defensive R13
  })

  it('deriveWriteStatus — 작성 완료 / 미작성', () => {
    expect(deriveWriteStatus({ status: 'approved' }).value).toBe('written')
    expect(deriveWriteStatus({ status: 'needs_revision' }).value).toBe('written')
    expect(deriveWriteStatus({ status: 'blocked' }).value).toBe('unwritten')
    expect(deriveWriteStatus(undefined).value).toBe('unwritten')
  })

  it('countNeedsRevision', () => {
    expect(countNeedsRevision({
      'I-1': { status: 'approved' },
      'II-1': { status: 'needs_revision' },
      'III-1': { status: 'needs_revision' },
      'IV-1': { status: 'draft' },
    })).toBe(2)
  })

  it('deriveEvidence — used_evidence_ids 검사', () => {
    const mr = { question_mappings: [
      { question_id: 'I-1', used_evidence_ids: ['e1'] },
      { question_id: 'II-1', used_evidence_ids: [] },
    ]}
    expect(deriveEvidence('I-1', mr).value).toBe('has')
    expect(deriveEvidence('II-1', mr).value).toBe('none')
    expect(deriveEvidence('UNKNOWN', mr).value).toBe('none')
    expect(deriveEvidence('I-1', null).value).toBe('none')  // null safety
  })

  it('deriveMissing — 우선순위 (open > deferred > resolved > none)', () => {
    const mm = [
      { question_id: 'Q1', status: 'open' },
      { question_id: 'Q1', status: 'resolved' },
      { question_id: 'Q2', status: 'deferred' },
      { question_id: 'Q3', status: 'rejected' },
    ]
    expect(deriveMissing('Q1', mm).value).toBe('open')
    expect(deriveMissing('Q2', mm).value).toBe('deferred')
    expect(deriveMissing('Q3', mm).value).toBe('resolved')  // rejected → resolved 그룹
    expect(deriveMissing('Q4', mm).value).toBe('none')
  })
})

describe('reviewAdapter — computeCriterionProgress scope 분기', () => {
  const fd = {
    sections: [
      { id: 'S1', questions: [{ id: 'I-1' }, { id: 'I-2' }] },
      { id: 'S2', questions: [{ id: 'II-1' }, { id: 'II-2' }] },
    ]
  }
  const drafts = {
    'I-1': { status: 'approved' },
    'I-2': { status: 'generated' },
    'II-1': { status: 'draft' },
    'II-2': { status: 'approved' },
  }

  it('scope=question — 매핑된 question_id 직접 집계', () => {
    expect(computeCriterionProgress(
      { scope: 'question', mapped_questions: ['I-1', 'II-1'] }, fd, drafts
    )).toEqual({ completed: 1, total: 2, scope_label: '문항' })
  })

  it('scope=section — 매핑 question이 속한 section 전체', () => {
    expect(computeCriterionProgress(
      { scope: 'section', mapped_questions: ['I-1'] }, fd, drafts
    )).toEqual({ completed: 2, total: 2, scope_label: '섹션' })
  })

  it('scope=document — 전체 DraftItem', () => {
    expect(computeCriterionProgress(
      { scope: 'document', mapped_questions: [] }, fd, drafts
    )).toEqual({ completed: 3, total: 4, scope_label: '문서' })
  })

  it('mapped_questions 객체 형식 처리 (R4 defensive)', () => {
    expect(computeCriterionProgress(
      { scope: 'question', mapped_questions: [{ question_id: 'I-1' }, { qid: 'II-1' }] }, fd, drafts
    ).completed).toBe(1)
  })

  it('scope 미정 → question fallback', () => {
    expect(computeCriterionProgress(
      { mapped_questions: ['I-1'] }, fd, drafts
    ).scope_label).toBe('문항')
  })
})

describe('reviewAdapter — buildChecklist 3단계 fallback', () => {
  it('fallback 1: noticeApiResp.required_documents', () => {
    const cl = buildChecklist({ required_documents: ['신청서', '재무제표'] })
    expect(cl).toHaveLength(2)
    expect(cl[0]._source).toBe('api')
  })

  it('fallback 2: snapshot.required_docs', () => {
    const cl = buildChecklist(null, { required_docs: ['보안서약서'] })
    expect(cl).toHaveLength(1)
    expect(cl[0]._source).toBe('snapshot')
  })

  it('fallback 3: 기본 4개', () => {
    const cl = buildChecklist(null, null)
    expect(cl).toHaveLength(4)
    expect(cl[0]._source).toBe('default')
  })
})

describe('reviewAdapter — computeWriteSummary 마감일 4단계', () => {
  const fd = { sections: [{ questions: [{ id: 'I-1' }] }] }
  const drafts = { 'I-1': { status: 'approved', content: 'abc', evidenceIds: ['e1'] } }
  const mr = { question_mappings: [{ question_id: 'I-1', used_evidence_ids: ['e1'] }] }

  it('fallback 1: noticeApiResp.deadline', () => {
    expect(computeWriteSummary(fd, drafts, mr, { deadline: '2026-06-15' }, null).deadline).toBe('2026-06-15')
  })

  it('fallback 2: selectedNotice.deadline', () => {
    expect(computeWriteSummary(fd, drafts, mr, null, { deadline: '2026-07-01' }).deadline).toBe('2026-07-01')
  })

  it('fallback 3: selectedNotice.date', () => {
    expect(computeWriteSummary(fd, drafts, mr, null, { date: '2026-08-01' }).deadline).toBe('2026-08-01')
  })

  it('fallback 4: "-"', () => {
    expect(computeWriteSummary(fd, drafts, mr, null, null).deadline).toBe('-')
  })

  it('통계 정합성', () => {
    const s = computeWriteSummary(fd, drafts, mr, null, null)
    expect(s.total).toBe(1)
    expect(s.approved).toBe(1)
    expect(s.evidenceLinkedCount).toBe(1)
    expect(s.evidenceCount).toBe(1)
  })
})

describe('reviewAdapter — computeMaterialsSummary', () => {
  it('Missing 4 + Supplemental 4 status count', () => {
    const ms = computeMaterialsSummary(
      [{ status: 'open' }, { status: 'resolved' }, { status: 'deferred' }, { status: 'rejected' }],
      [{ status: 'uploaded' }, { status: 'converted' }]
    )
    expect(ms.missing).toEqual({ open: 1, resolved: 1, deferred: 1, rejected: 1 })
    expect(ms.supplemental).toEqual({ uploaded: 1, analyzed: 0, converted: 1, failed: 0 })
  })

  it('open 항목 펼침', () => {
    const ms = computeMaterialsSummary(
      [{ question_id: 'Q1', status: 'open' }, { question_id: 'Q2', status: 'resolved' }],
      []
    )
    expect(ms.openItems).toHaveLength(1)
    expect(ms.openItems[0].question_id).toBe('Q1')
  })
})

// ─────────────────────────────────────────────────────────────────────
// 4. runtimeLog (handleFallback + DISABLE_FALLBACK)
// ─────────────────────────────────────────────────────────────────────
describe('runtimeLog', () => {
  it('logApi — console.log 호출', () => {
    const spy = vi.spyOn(console, 'log').mockImplementation(() => {})
    logApi('test', { foo: 'bar' })
    expect(spy).toHaveBeenCalledWith('[REAL_API] test', { foo: 'bar' })
    spy.mockRestore()
  })

  it('handleFallback — DISABLE_FALLBACK=false (default) → fallback 반환 + warn', () => {
    const spy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const onError = vi.fn()
    const result = handleFallback('test', new Error('boom'), { onError })
    // DISABLE_FALLBACK=false (test env에선 set 안 됨) → 'fallback' 반환
    expect(result).toBe('fallback')
    expect(spy).toHaveBeenCalled()
    expect(onError).not.toHaveBeenCalled()  // false 모드는 onError 호출 X
    spy.mockRestore()
  })

  it('isFallbackBlocked — 기본 false (env 없음)', () => {
    expect(isFallbackBlocked()).toBe(false)
  })
})

// ─────────────────────────────────────────────────────────────────────
// 5. form/notice adapter null safety
//   (Step2Analysis 내부 함수라 직접 import 불가 — 핵심 패턴만 검증)
//   adapter들이 missing/null 입력 시 throw 없이 처리하는지
// ─────────────────────────────────────────────────────────────────────
describe('adapter null safety (간접 검증)', () => {
  it('adaptMissingItems undefined → []', () => {
    expect(adaptMissingItems(undefined, 'I-1')).toEqual([])
  })

  it('adaptAutoMatchedCards undefined → []', () => {
    expect(adaptAutoMatchedCards(undefined)).toEqual([])
  })

  it('deriveSufficiency null → 0/0/0', () => {
    expect(deriveSufficiency(null).total).toBe(0)
  })

  it('findQuestionMeta — formData 없을 때 null', () => {
    expect(findQuestionMeta('I-1', null)).toBeNull()
    expect(findQuestionMeta('I-1', { sections: [] })).toBeNull()
  })

  it('adaptSelectedQuestion — selectedQid 미존재 → null', () => {
    expect(adaptSelectedQuestion(null, null)).toBeNull()
    expect(adaptSelectedQuestion('UNKNOWN', { sections: [{ questions: [] }] })).toBeNull()
  })

  it('computeWriteSummary — formData/drafts/mappingResult null safety', () => {
    const s = computeWriteSummary(null, null, null, null, null)
    expect(s.total).toBe(0)
    expect(s.approved).toBe(0)
    expect(s.deadline).toBe('-')
  })

  it('computeCriterionProgress — formData/drafts null', () => {
    const out = computeCriterionProgress(
      { scope: 'document', mapped_questions: [] }, null, null
    )
    expect(out.total).toBe(0)
    expect(out.completed).toBe(0)
  })

  it('deriveMissing — missingMaterials null/undefined', () => {
    expect(deriveMissing('Q1', null).value).toBe('none')
    expect(deriveMissing('Q1', undefined).value).toBe('none')
  })
})
