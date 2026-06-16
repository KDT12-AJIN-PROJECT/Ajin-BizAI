// Phase 4-H A.1 — frontend adapter 함수 단위 검증 (dependency-free)
//
// Node ES Modules로 lib/*.js 직접 import.
// vitest/jest 의존 X — 단순 print + throw on assert fail.
//
// 실행:
//   cd web-react
//   node tests/adapters.mjs
//
// 검증 대상 adapter:
//   - lib/sessionStatus.js: statusToStep / resolveSessionStep / ACTIVE_STATUSES
//   - lib/missingAdapter.js: adaptMissingItems / adaptAutoMatchedCards / deriveSufficiency
//   - lib/reviewAdapter.js: groupDraftStatus / deriveWriteStatus / deriveEvidence
//                          / deriveMissing / computeCriterionProgress / buildChecklist
//                          / computeWriteSummary / computeMaterialsSummary / countNeedsRevision

import {
  SESSION_STATUS, ACTIVE_STATUSES, statusToStep, resolveSessionStep, isActiveStatus,
} from '../src/lib/sessionStatus.js'
import {
  adaptMissingItems, adaptAutoMatchedCards, adaptPendingMatchCards, deriveSufficiency,
} from '../src/lib/missingAdapter.js'
import {
  groupDraftStatus, deriveWriteStatus, deriveEvidence, deriveMissing,
  computeCriterionProgress, buildChecklist, computeWriteSummary, computeMaterialsSummary,
  countNeedsRevision,
} from '../src/lib/reviewAdapter.js'

const results = { pass: 0, fail: 0, errors: [] }

function eq(actual, expected, label) {
  const a = JSON.stringify(actual)
  const e = JSON.stringify(expected)
  if (a === e) {
    results.pass++
    console.log(`  PASS ${label}`)
  } else {
    results.fail++
    results.errors.push(`[FAIL] ${label}\n    expected: ${e}\n    actual:   ${a}`)
    console.log(`  FAIL ${label}`)
    console.log(`    expected: ${e}`)
    console.log(`    actual:   ${a}`)
  }
}

function truthy(v, label) {
  if (v) { results.pass++; console.log(`  PASS ${label}`) }
  else { results.fail++; console.log(`  FAIL ${label} (got ${v})`) }
}

// ─────────────────────────────────────────────────────────────
console.log('='.repeat(64))
console.log(' Phase 4-G smoke test (A.1 — frontend adapter 함수)')
console.log('='.repeat(64))

// 1. sessionStatus
console.log('\n[sessionStatus]')
eq(statusToStep('created'), 1, 'statusToStep(created) = 1')
eq(statusToStep('analyzing'), 2, 'statusToStep(analyzing) = 2')
eq(statusToStep('analysis_ready'), 2, 'statusToStep(analysis_ready) = 2')
eq(statusToStep('step2_confirmed'), 3, 'statusToStep(step2_confirmed) = 3')
eq(statusToStep('drafting'), 3, 'statusToStep(drafting) = 3')
eq(statusToStep('completed'), 5, 'statusToStep(completed) = 5')
eq(statusToStep('abandoned'), null, 'statusToStep(abandoned) = null')
eq(isActiveStatus('drafting'), true, 'isActiveStatus(drafting) = true')
eq(isActiveStatus('completed'), false, 'isActiveStatus(completed) = false')

// resolveSessionStep — current_step 우선
eq(resolveSessionStep({ status: 'drafting', current_step: 3 }), 3, 'resolveSessionStep(drafting, step=3) = 3')
eq(resolveSessionStep({ status: 'drafting', current_step: 99 }), 3, 'resolveSessionStep invalid current_step → status mapping')
eq(resolveSessionStep({ status: 'unknown', current_step: 0 }), 1, 'resolveSessionStep unknown → 1')

// 2. missingAdapter
console.log('\n[missingAdapter]')
const missingMaterials = [
  { missing_id: 'm1', question_id: 'II-1', name: '시장 데이터', description: '...', input_type: 'file', status: 'open' },
  { missing_id: 'm2', question_id: 'I-1', name: '재무제표', input_type: 'text', status: 'resolved' },  // 필터됨 (resolved)
  { missing_id: 'm3', question_id: 'II-1', name: '경쟁사 비교', input_type: 'either', status: 'open' },
]
const filtered = adaptMissingItems(missingMaterials, 'II-1')
eq(filtered.length, 2, 'adaptMissingItems(II-1) length = 2 (resolved 필터)')
eq(filtered[0].id, 'm1', 'adaptMissingItems[0].id = m1')
eq(filtered[0].actions.length > 0, true, 'adaptMissingItems actions 채워짐')

const bulkResults = [
  { supplemental_id: 's1', file_name: 'a.pdf', target_question_id: 'I-1', confidence: 0.85, auto_match: true, status: 'analyzed' },
  { supplemental_id: 's2', file_name: 'b.pdf', target_question_id: 'I-2', confidence: 0.65, auto_match: false, status: 'uploaded' },
]
const autoCards = adaptAutoMatchedCards(bulkResults)
const pendingCards = adaptPendingMatchCards(bulkResults)
eq(autoCards.length, 1, 'adaptAutoMatchedCards length = 1')
eq(pendingCards.length, 1, 'adaptPendingMatchCards length = 1')

const formDataStatus = {
  sections: [
    { id: 'S1', questions: [
      { id: 'I-1', status: 'ok' },
      { id: 'II-1', status: 'weak' },
      { id: 'III-1', status: 'missing' },
    ]}
  ]
}
const suf = deriveSufficiency(formDataStatus)
eq(suf.ok, 1, 'deriveSufficiency.ok = 1')
eq(suf.weak, 1, 'deriveSufficiency.weak = 1')
eq(suf.missing, 1, 'deriveSufficiency.missing = 1')
eq(suf.total, 3, 'deriveSufficiency.total = 3')

// 3. reviewAdapter — groupDraftStatus
console.log('\n[reviewAdapter — groupDraftStatus]')
eq(groupDraftStatus('approved'), 'approved', 'approved → approved')
eq(groupDraftStatus('generated'), 'written', 'generated → written')
eq(groupDraftStatus('user_edited'), 'written', 'user_edited → written')
eq(groupDraftStatus('needs_revision'), 'written', 'needs_revision → written')
eq(groupDraftStatus('draft'), 'unwritten', 'draft → unwritten')
eq(groupDraftStatus('blocked'), 'unwritten', 'blocked → unwritten')
eq(groupDraftStatus('unknown_status'), 'unwritten', 'unknown → unwritten (defensive R13)')

// deriveWriteStatus
console.log('\n[reviewAdapter — deriveWriteStatus]')
eq(deriveWriteStatus({ status: 'approved' }).value, 'written', 'approved → written label')
eq(deriveWriteStatus({ status: 'blocked' }).value, 'unwritten', 'blocked → unwritten label')
eq(deriveWriteStatus(undefined).value, 'unwritten', 'undefined → unwritten')

// countNeedsRevision
console.log('\n[reviewAdapter — countNeedsRevision]')
eq(countNeedsRevision({
  'I-1': { status: 'approved' },
  'II-1': { status: 'needs_revision' },
  'III-1': { status: 'needs_revision' },
  'IV-1': { status: 'draft' },
}), 2, 'countNeedsRevision = 2')

// deriveEvidence
console.log('\n[reviewAdapter — deriveEvidence]')
const mr = { question_mappings: [
  { question_id: 'I-1', used_evidence_ids: ['e1', 'e2'] },
  { question_id: 'II-1', used_evidence_ids: [] },
]}
eq(deriveEvidence('I-1', mr).value, 'has', 'deriveEvidence I-1 = has')
eq(deriveEvidence('II-1', mr).value, 'none', 'deriveEvidence II-1 = none (empty)')
eq(deriveEvidence('UNKNOWN', mr).value, 'none', 'deriveEvidence UNKNOWN = none (mapping 없음)')

// deriveMissing — 우선순위 규칙
console.log('\n[reviewAdapter — deriveMissing 우선순위 규칙]')
const mm = [
  { missing_id: 'a', question_id: 'Q1', status: 'open' },
  { missing_id: 'b', question_id: 'Q1', status: 'resolved' },
  { missing_id: 'c', question_id: 'Q2', status: 'resolved' },
  { missing_id: 'd', question_id: 'Q3', status: 'deferred' },
  { missing_id: 'e', question_id: 'Q3', status: 'resolved' },
  { missing_id: 'f', question_id: 'Q4', status: 'rejected' },
]
eq(deriveMissing('Q1', mm).value, 'open', 'Q1 (open + resolved) → open')
eq(deriveMissing('Q2', mm).value, 'resolved', 'Q2 (resolved만) → resolved')
eq(deriveMissing('Q3', mm).value, 'deferred', 'Q3 (deferred + resolved) → deferred')
eq(deriveMissing('Q4', mm).value, 'resolved', 'Q4 (rejected) → resolved 그룹')
eq(deriveMissing('Q5', mm).value, 'none', 'Q5 (없음) → none')

// computeCriterionProgress — scope 분기 (정책 #4)
console.log('\n[reviewAdapter — computeCriterionProgress scope 분기]')
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
const cq = computeCriterionProgress(
  { scope: 'question', mapped_questions: ['I-1', 'II-1'] },
  fd, drafts
)
eq(cq, { completed: 1, total: 2, scope_label: '문항' }, 'scope=question (I-1 approved + II-1 draft)')

const cs = computeCriterionProgress(
  { scope: 'section', mapped_questions: ['I-1'] },
  fd, drafts
)
eq(cs, { completed: 2, total: 2, scope_label: '섹션' }, 'scope=section S1 (I-1, I-2 모두 written)')

const cd = computeCriterionProgress(
  { scope: 'document', mapped_questions: [] },
  fd, drafts
)
eq(cd, { completed: 3, total: 4, scope_label: '문서' }, 'scope=document (3/4 written)')

// mapped_questions가 object 배열인 경우 (R4 defensive)
const cq2 = computeCriterionProgress(
  { scope: 'question', mapped_questions: [{ question_id: 'I-1' }, { qid: 'II-1' }] },
  fd, drafts
)
eq(cq2.completed, 1, 'scope=question with object mapped_questions (R4)')

// buildChecklist — fallback 3단계
console.log('\n[reviewAdapter — buildChecklist 3단계 fallback]')
const cl1 = buildChecklist({ required_documents: ['신청서', '재무제표'] })
eq(cl1.length, 2, 'fallback 1: noticeApiResp.required_documents (2개)')
eq(cl1[0]._source, 'api', 'fallback 1: _source = api')

const cl2 = buildChecklist(null, { required_docs: ['보안서약서'] })
eq(cl2.length, 1, 'fallback 2: snapshot.required_docs (1개)')
eq(cl2[0]._source, 'snapshot', 'fallback 2: _source = snapshot')

const cl3 = buildChecklist(null, null)
eq(cl3.length, 4, 'fallback 3: 기본 4개')
eq(cl3[0]._source, 'default', 'fallback 3: _source = default')

// computeWriteSummary — 마감일 fallback 4단계
console.log('\n[reviewAdapter — computeWriteSummary 마감일 fallback]')
const ws1 = computeWriteSummary(fd, drafts, mr, { deadline: '2026-06-15' }, null)
eq(ws1.deadline, '2026-06-15', 'fallback 1: noticeApiResp.deadline')

const ws2 = computeWriteSummary(fd, drafts, mr, null, { deadline: '2026-07-01' })
eq(ws2.deadline, '2026-07-01', 'fallback 2: selectedNotice.deadline')

const ws3 = computeWriteSummary(fd, drafts, mr, null, { date: '2026-08-01' })
eq(ws3.deadline, '2026-08-01', 'fallback 3: selectedNotice.date')

const ws4 = computeWriteSummary(fd, drafts, mr, null, null)
eq(ws4.deadline, '-', 'fallback 4: "-"')

// 통계 정합성
eq(ws1.total, 4, 'computeWriteSummary.total = 4')
eq(ws1.approved, 2, 'computeWriteSummary.approved = 2')
eq(ws1.written, 1, 'computeWriteSummary.written = 1 (generated)')
eq(ws1.unwritten, 1, 'computeWriteSummary.unwritten = 1 (draft)')
eq(ws1.evidenceLinkedCount, 1, 'computeWriteSummary.evidenceLinkedCount = 1 (I-1만 used_evidence>0)')

// computeMaterialsSummary
console.log('\n[reviewAdapter — computeMaterialsSummary]')
const ms = computeMaterialsSummary(
  [
    { question_id: 'Q1', status: 'open', name: 'A' },
    { question_id: 'Q2', status: 'resolved' },
    { question_id: 'Q3', status: 'deferred' },
    { question_id: 'Q4', status: 'rejected' },
  ],
  [
    { supplemental_id: 's1', status: 'uploaded' },
    { supplemental_id: 's2', status: 'converted' },
  ]
)
eq(ms.missing, { open: 1, resolved: 1, deferred: 1, rejected: 1 }, 'missing 4 status count')
eq(ms.supplemental, { uploaded: 1, analyzed: 0, converted: 1, failed: 0 }, 'supplemental 4 status count')
eq(ms.openItems.length, 1, 'openItems = 1')

// summary
console.log()
console.log('='.repeat(64))
console.log(` RESULT: ${results.pass} / ${results.pass + results.fail} passed (${results.fail} failed)`)
console.log('='.repeat(64))
if (results.fail > 0) {
  console.log('\nFAILURES:')
  results.errors.forEach(e => console.log(`  ${e}`))
  process.exit(1)
}
process.exit(0)
