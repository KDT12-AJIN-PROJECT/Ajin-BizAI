// AJIN BizAI v0.2 — Step 4 검토 화면 adapter (Phase 4-G-7b)
// 출처: PRD §11.1 (v0.2 평가 엔진 X) + PRD-13 §18.10
//
// 정책: V1 Step4Review / /api/ai/evaluate / V1 5섹션 구조 사용 금지.
// V2는 FormSchema + DraftItem + question_id 기준만.

// ─── 1. 작성 상태 그룹화 (3 segments — statistics 카드 ② 통합) ───
const WRITTEN_STATUSES = ['generated', 'user_edited', 'needs_revision']
const APPROVED_STATUSES = ['approved']
// 'draft', 'blocked' → unwritten / 알 수 없는 status도 unwritten으로 (defensive, R13)

export function groupDraftStatus(status) {
  if (APPROVED_STATUSES.includes(status)) return 'approved'
  if (WRITTEN_STATUSES.includes(status)) return 'written'
  return 'unwritten'  // draft / blocked / unknown
}

// ─── 2. 문항 테이블 — 작성 상태 (2값: 작성 완료 / 미작성) ───
export function deriveWriteStatus(draft) {
  const s = draft?.status || 'draft'
  if (APPROVED_STATUSES.includes(s) || WRITTEN_STATUSES.includes(s)) {
    return { value: 'written', label: '작성 완료' }
  }
  return { value: 'unwritten', label: '미작성' }
}

// needs_revision count (R3 — 모달에 별도 표시)
export function countNeedsRevision(drafts) {
  return Object.values(drafts || {}).filter(d => d?.status === 'needs_revision').length
}

// ─── 3. 문항 테이블 — Evidence (2값: 있음 / 없음) ───
export function deriveEvidence(questionId, mappingResult) {
  if (!mappingResult?.question_mappings) return { value: 'none', label: '근거자료 없음' }
  const m = mappingResult.question_mappings.find(qm => qm.question_id === questionId)
  const has = (m?.used_evidence_ids?.length || 0) > 0
  return has
    ? { value: 'has', label: '근거자료 있음' }
    : { value: 'none', label: '근거자료 없음' }
}

// ─── 4. 문항 테이블 — 부족자료 (4값, 우선순위 규칙) ───
export function deriveMissing(questionId, missingMaterials) {
  const items = (missingMaterials || []).filter(m => m.question_id === questionId)
  if (items.length === 0) return { value: 'none', label: '없음' }
  if (items.some(m => m.status === 'open')) {
    return { value: 'open', label: '부족자료 open' }
  }
  if (items.some(m => m.status === 'deferred')) {
    return { value: 'deferred', label: '부족자료 deferred' }
  }
  // resolved + rejected는 같은 그룹
  return { value: 'resolved', label: '부족자료 resolved' }
}

// ─── 5. 평가기준별 작성 완료 수 / 전체 매핑 수 (scope 분기, 정책 #4) ───
// V1 5섹션 enum 변환 X. FormSchema question_id + DraftItem 기준.
export function computeCriterionProgress(criterion, formData, drafts) {
  const isWritten = (qid) => {
    const status = drafts?.[qid]?.status
    return APPROVED_STATUSES.includes(status) || WRITTEN_STATUSES.includes(status)
  }

  // mapped_questions가 string[]일 수도 object[]일 수도 (R4 defensive)
  const extractQid = (mq) => {
    if (typeof mq === 'string') return mq
    return mq?.question_id || mq?.qid || null
  }

  switch (criterion.scope) {
    case 'question': {
      const qids = (criterion.mapped_questions || []).map(extractQid).filter(Boolean)
      const total = qids.length
      const completed = qids.filter(isWritten).length
      return { completed, total, scope_label: '문항' }
    }
    case 'section': {
      const qids = (criterion.mapped_questions || []).map(extractQid).filter(Boolean)
      const sectionIds = new Set()
      ;(formData?.sections || []).forEach(sec => {
        if (sec.questions.some(q => qids.includes(q.id))) {
          sectionIds.add(sec.id)
        }
      })
      const allInSections = (formData?.sections || [])
        .filter(sec => sectionIds.has(sec.id))
        .flatMap(sec => sec.questions.map(q => q.id))
      const total = allInSections.length
      const completed = allInSections.filter(isWritten).length
      return { completed, total, scope_label: '섹션' }
    }
    case 'document': {
      const allQids = (formData?.sections || []).flatMap(sec => sec.questions.map(q => q.id))
      const total = allQids.length
      const completed = allQids.filter(isWritten).length
      return { completed, total, scope_label: '문서' }
    }
    default:
      // scope 미정 시 question으로 fallback (defensive)
      return computeCriterionProgress({ ...criterion, scope: 'question' }, formData, drafts)
  }
}

// ─── 6. 사전 점검 체크리스트 — 동적 + fallback 3단계 ───
// 1순위: noticeApiResp.required_documents
// 2순위: notice_schema_json.snapshot.required_docs (restore 케이스)
// 3순위: 기본 4개
const DEFAULT_CHECKLIST = [
  '공고 마감일을 확인했음',
  '필수 제출서류를 확인했음',
  '사업자등록증 / 재무제표 등 첨부자료를 준비했음',
  '누락 정보 또는 부족자료를 검토했음',
]

export function buildChecklist(noticeApiResp, snapshot) {
  const fromApi = noticeApiResp?.required_documents
  if (Array.isArray(fromApi) && fromApi.length > 0) {
    return fromApi.map((doc, i) => ({ id: `req_${i}`, label: doc, _source: 'api' }))
  }
  const fromSnapshot = snapshot?.required_docs || snapshot?.required_documents
  if (Array.isArray(fromSnapshot) && fromSnapshot.length > 0) {
    return fromSnapshot.map((doc, i) => ({ id: `snap_${i}`, label: doc, _source: 'snapshot' }))
  }
  return DEFAULT_CHECKLIST.map((label, i) => ({ id: `default_${i}`, label, _source: 'default' }))
}

// ─── 7. 작성 요약 통계 (6 카드, status 3 segments 통합) ───
export function computeWriteSummary(formData, drafts, mappingResult, noticeApiResp, selectedNotice) {
  const allQids = (formData?.sections || []).flatMap(sec => sec.questions.map(q => q.id))
  const total = allQids.length

  let approved = 0, written = 0, unwritten = 0
  let totalChars = 0
  const evidenceSet = new Set()
  let evidenceLinkedCount = 0

  allQids.forEach(qid => {
    const d = drafts?.[qid]
    const group = groupDraftStatus(d?.status)
    if (group === 'approved') approved++
    else if (group === 'written') written++
    else unwritten++

    totalChars += (d?.content?.length || 0)
    if (Array.isArray(d?.evidenceIds)) {
      d.evidenceIds.forEach(id => evidenceSet.add(id))
    }
  })

  // Evidence 연결 문항 수 — mappingResult 기준
  ;(mappingResult?.question_mappings || []).forEach(m => {
    if ((m.used_evidence_ids?.length || 0) > 0) evidenceLinkedCount++
  })

  // 마감일 fallback 4단계 (A.1)
  // 1: noticeApiResp.deadline / 2: selectedNotice.deadline|date / 3: snapshot.deadline / 4: "-"
  let deadline = '-'
  if (noticeApiResp?.deadline) deadline = noticeApiResp.deadline
  else if (selectedNotice?.deadline) deadline = selectedNotice.deadline
  else if (selectedNotice?.date) deadline = selectedNotice.date

  return {
    total,
    written,
    approved,
    unwritten,
    totalChars,
    evidenceCount: evidenceSet.size,
    evidenceLinkedCount,
    deadline,
  }
}

// ─── 8. Missing / Supplemental status 요약 (5 영역 ⑤) ───
export function computeMaterialsSummary(missingMaterials, supplementalMaterials) {
  const missing = { open: 0, resolved: 0, deferred: 0, rejected: 0 }
  ;(missingMaterials || []).forEach(m => {
    if (m.status === 'open') missing.open++
    else if (m.status === 'resolved') missing.resolved++
    else if (m.status === 'deferred') missing.deferred++
    else if (m.status === 'rejected') missing.rejected++
  })

  const supplemental = { uploaded: 0, analyzed: 0, converted: 0, failed: 0 }
  ;(supplementalMaterials || []).forEach(s => {
    if (s.status === 'uploaded') supplemental.uploaded++
    else if (s.status === 'analyzed') supplemental.analyzed++
    else if (s.status === 'converted') supplemental.converted++
    else if (s.status === 'failed') supplemental.failed++
  })

  // open 항목 펼침용 (question_id 별 그룹)
  const openItems = (missingMaterials || []).filter(m => m.status === 'open')

  return { missing, supplemental, openItems }
}
