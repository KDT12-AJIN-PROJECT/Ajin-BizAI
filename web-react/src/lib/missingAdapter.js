// AJIN BizAI v0.2 — Step 2 SupplementalPanel adapter (Phase 4-G-7a)
// 출처: PRD §13.6 MissingMaterial / SupplementalMaterial + PRD-13 §18.10

// ─── 1. backend MissingMaterial[] → SUPPLEMENTAL_MOCK.missingItems shape ───
// selectedQid 필터 + input_type에 따라 액션 결정
const ACTIONS_BY_TYPE = {
  text: ['직접입력', '원문보기', '나중에'],
  file: ['파일업로드', '원문보기', '나중에'],
  either: ['직접입력', '파일업로드', '원문보기', '나중에'],
}

function getActionsForType(inputType) {
  return ACTIONS_BY_TYPE[inputType] || ACTIONS_BY_TYPE.either
}

export function adaptMissingItems(missingMaterials, selectedQid) {
  if (!Array.isArray(missingMaterials)) return []
  return missingMaterials
    .filter(m => m.question_id === selectedQid && m.status !== 'resolved' && m.status !== 'rejected')
    .map(m => ({
      id: m.missing_id,
      label: m.name,
      desc: m.description || m.missing_type || '',
      actions: getActionsForType(m.input_type),
      _raw: m,  // backend 원본 보존 (액션 시 missing_id 등 사용)
    }))
}

// ─── 2. bulk-upload 응답 → matchAuto / matchUserPriority 카드 shape ───
export function adaptAutoMatchedCards(bulkResults) {
  if (!Array.isArray(bulkResults)) return []
  return bulkResults
    .filter(r => r.auto_match === true || r.confidence >= 0.70)
    .map(r => ({
      status: 'confirmed',
      supplemental_id: r.supplemental_id,
      qid: r.target_question_id,
      confidence: Math.round((r.confidence || 0) * 100),
      confLevel: (r.confidence || 0) >= 0.85 ? 'high' : 'mid',
      file: r.file_name,
      tag: '✓ 자동 확정',
    }))
}

export function adaptPendingMatchCards(bulkResults) {
  if (!Array.isArray(bulkResults)) return []
  return bulkResults
    .filter(r => !r.auto_match && r.confidence < 0.70)
    .map(r => ({
      status: 'pending',
      supplemental_id: r.supplemental_id,
      qid: r.target_question_id,
      confidence: Math.round((r.confidence || 0) * 100),
      confLevel: 'mid',
      file: r.file_name,
      desc: `confidence ${Math.round((r.confidence || 0) * 100)}% — 사용자 확인 필요`,
    }))
}

// ─── 3. formData(applyStatusToForm 적용본) → sufficiency 통계 ───
// deriveStatusStats는 Step2Analysis에 있으므로 인라인 계산
export function deriveSufficiency(formDataWithStatus) {
  if (!formDataWithStatus?.sections) {
    return { ok: 0, weak: 0, missing: 0, total: 0, percent: 0 }
  }
  let ok = 0, weak = 0, missing = 0
  formDataWithStatus.sections.forEach(sec => {
    sec.questions.forEach(q => {
      if (q.status === 'missing') missing++
      else if (q.status === 'weak') weak++
      else ok++
    })
  })
  const total = ok + weak + missing
  const percent = total > 0 ? Math.round(((ok + weak * 0.5) / total) * 100) : 0
  return { ok, weak, missing, total, percent }
}

// ─── 4. selectedQid에 해당하는 question meta (formData에서 lookup) ───
export function findQuestionMeta(selectedQid, formData) {
  if (!formData?.sections) return null
  for (const sec of formData.sections) {
    const q = sec.questions.find(x => x.id === selectedQid)
    if (q) return { ...q, sectionTitle: sec.title }
  }
  return null
}

// ─── 5. SUPPLEMENTAL_MOCK.selected shape으로 변환 ───
const STATUS_LABEL_KR = {
  ok: '작성 가능',
  weak: '근거 부족',
  missing: '자료 없음',
}

export function adaptSelectedQuestion(selectedQid, formData) {
  const q = findQuestionMeta(selectedQid, formData)
  if (!q) return null
  return {
    qid: q.id,
    name: q.title,
    status: q.status,
    statusLabel: STATUS_LABEL_KR[q.status] || q.status,
  }
}
