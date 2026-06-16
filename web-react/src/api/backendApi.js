/**
 * FastAPI 백엔드 연동 API client
 * 상대 경로 사용 — Vite proxy / Express proxy 모두 통해서 FastAPI:8000 으로 전달됩니다.
 */

const BASE = ''

async function req(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body !== undefined) opts.body = JSON.stringify(body)
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

// ── Notices ──────────────────────────────────────────────
export const noticesApi = {
  getAll: () => req('GET', '/api/notices'),
  bulkUpsert: (notices) => req('POST', '/api/notices/bulk', notices),
  getById: (id) => req('GET', `/api/notices/by-id?id=${encodeURIComponent(id)}`),
}

// ── Drafts ───────────────────────────────────────────────
/**
 * @deprecated Legacy Draft API (v3.2 M-0).
 * 신규 작성 흐름에서는 ApplicationSession 기반 analysisApi
 * (예: getDraftItems, initializeDraftItems, getStep3Ready)를 사용한다.
 */
export const draftsApi = {
  // 기존 DraftPage 호환 (notice_id 기반)
  getAll: () => req('GET', '/api/drafts'),
  get: (noticeId) => req('GET', `/api/drafts/${encodeURIComponent(noticeId)}`),
  upsert: (noticeId, data) => req('PUT', `/api/drafts/${encodeURIComponent(noticeId)}`, {
    notice_id: noticeId,
    ...data,
  }),
  remove: (noticeId) => req('DELETE', `/api/drafts/${encodeURIComponent(noticeId)}`),

  // MyDraftsPage / ArchivePage용 (버전 관리)
  list: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null))
    ).toString()
    return req('GET', `/api/drafts/list${qs ? '?' + qs : ''}`)
  },
  createVersion: (noticeId, body = {}) =>
    req('POST', `/api/drafts/${encodeURIComponent(noticeId)}/versions`, body),

  // draft_id(정수 PK) 기반 상태/결과/보관 조작
  updateStatus: (draftId, status, resultMemo) =>
    req('PUT', `/api/drafts/by-id/${draftId}/status`, { status, result_memo: resultMemo }),
  updateResult: (draftId, result, resultDate, resultMemo) =>
    req('PUT', `/api/drafts/by-id/${draftId}/result`, { result, result_date: resultDate, result_memo: resultMemo }),
  archive: (draftId) => req('PUT', `/api/drafts/by-id/${draftId}/archive`),
  restore: (draftId) => req('PUT', `/api/drafts/by-id/${draftId}/restore`),
  permanentDelete: (draftId) => req('DELETE', `/api/drafts/by-id/${draftId}/permanent`),
  permanentDeleteBulk: (ids) => req('DELETE', '/api/drafts/permanent/bulk', { ids }),
}

// v3.2 M-0: legacy alias — `draftsApi`와 동일 객체.
// `draftsApi === legacyDraftsApi` 보장. 신규 코드는 이 alias 사용 권장(의도 표시용).
export const legacyDraftsApi = draftsApi

// ── Bookmarks ─────────────────────────────────────────────
export const bookmarksApi = {
  getAll: () => req('GET', '/api/bookmarks'),
  add: (noticeId, noticeSnapshot = {}) =>
    req('POST', '/api/bookmarks', { notice_id: noticeId, notice_snapshot: noticeSnapshot }),
  remove: (noticeId) => req('DELETE', `/api/bookmarks/${encodeURIComponent(noticeId)}`),
  clearAll: () => req('DELETE', '/api/bookmarks'),
}

// ── Profile ───────────────────────────────────────────────
export const profileApi = {
  get: () => req('GET', '/api/profile'),
  save: (data) => req('PUT', '/api/profile', data),
}

// ── AI ─────────────────────────────────────────────────────
// React는 AI 모델을 직접 호출하지 않고 FastAPI를 통해서만 호출합니다.
//
// ⚠ DEPRECATED (PRD-13 §18.4) — V1 DraftPage 호환 전용.
// V2 (/draft-v2) 는 analysisApi (/api/analysis/*) + chatApi (/api/chat/draft-assist) 만 사용.
// V2 코드에서 aiApi 호출은 정책 위반. Phase 7 V1 폐기 시점에 generate/improve/chat-review/check-completeness 제거.
// aiApi.evaluate 만 v0.3 (Step 4 평가 엔진 분리) 까지 유지.
export const aiApi = {
  providerInfo: () => req('GET', '/api/ai/provider-info'),
  generateDraft: (noticeText, profile, section) =>
    req('POST', '/api/ai/generate-draft', { notice_text: noticeText, profile, section }),
  evaluate: (draftText, noticeText = '') =>
    req('POST', '/api/ai/evaluate', { draft_text: draftText, notice_text: noticeText }),
  improve: (draftText, instruction) =>
    req('POST', '/api/ai/improve', { draft_text: draftText, instruction }),
  checkCompleteness: (uploadedDocs, noticeText = '') =>
    req('POST', '/api/ai/check-completeness', { uploaded_docs: uploadedDocs, notice_text: noticeText }),
  chatReview: (message, draftContent, noticeTitle, history = []) =>
    req('POST', '/api/ai/chat-review', { message, draft_content: draftContent, notice_title: noticeTitle, history }),
}

// ── DraftPage 호환 래퍼 (lmStudioApi 동일 시그니처) ──────────────
// DraftPage에서 lmStudioApi 대신 이 함수들을 import하여 사용합니다.

const SECTION_LABEL_TO_KEY = {
  '신청 기업 개요': 'overview',
  '사업 참여 목적 및 필요성': 'purpose',
  '세부 추진 계획': 'plan',
  '기대 효과': 'effect',
  '예산 계획 개요': 'budget',
}

function noticeToText(notice) {
  return [
    `공고명: ${notice?.title || ''}`,
    `지원대상: ${notice?.target || ''}`,
    `지원내용: ${notice?.benefit || ''}`,
  ].join('\n')
}

function profileToDict(profileData) {
  if (!profileData) return {}
  return {
    company_name: profileData.companyName || profileData.company_name || '',
    field: profileData.field || '',
    summary: profileData.summary || '',
    strategy: profileData.strategy || '',
  }
}

export async function generateSubmissionDraft({ notice, section, uploadedData, profileData }) {
  const sectionKey = SECTION_LABEL_TO_KEY[section] || 'overview'
  const res = await req('POST', '/api/ai/generate-draft', {
    notice_text: noticeToText(notice),
    profile: profileToDict(profileData),
    section: sectionKey,
  })
  return res.text
}

export async function checkUploadCompleteness({ notice, uploads, profileData }) {
  const uploadedDocs = Object.fromEntries(
    Object.entries(uploads || {}).map(([cat, files]) => [
      cat,
      (files || []).map(f => f.name || String(f)).join(', '),
    ])
  )
  const res = await req('POST', '/api/ai/check-completeness', {
    uploaded_docs: uploadedDocs,
    notice_text: noticeToText(notice),
  })
  return JSON.stringify(res)
}

export async function evaluateDraft({ notice, drafts, profileData }) {
  const draftText = Object.entries(drafts || {})
    .filter(([, v]) => v?.trim())
    .map(([k, v]) => `[${k}]\n${v.slice(0, 400)}`)
    .join('\n\n')
  const res = await req('POST', '/api/ai/evaluate', {
    draft_text: draftText || '(아직 작성된 내용 없음)',
    notice_text: noticeToText(notice),
  })
  return JSON.stringify(res)
}

export async function applyImprovement({ section, currentText, improvedText, notice }) {
  const res = await req('POST', '/api/ai/improve', {
    draft_text: currentText || '',
    instruction: `[${section}] 다음 보완안 방향으로 재작성: ${improvedText}`,
  })
  return res.text
}

export async function chatWithDraftReviewer({ message, draftContent, notice, history = [] }) {
  const res = await req('POST', '/api/ai/chat-review', {
    message,
    draft_content: draftContent || '',
    notice_title: notice?.title || '',
    history: history.slice(-6).map(h => ({ role: h.role, content: h.content })),
  })
  return res.response
}

// ── v0.2 Analysis API (PRD §16) ────────────────────────────
// DraftPageV2 (/draft-v2) → /api/analysis/* + /api/chat/* 호출
// Phase 4-G에서 frontend mock → 실제 API로 점진 교체
export const analysisApi = {
  // Phase 4-G-0.5: ApplicationSession 생성 (DB 영속)
  createSession: ({ userId = 'anonymous', noticeId = null, noticeSnapshot = null, initialStep = 1 } = {}) =>
    req('POST', '/api/analysis/sessions', {
      user_id: userId,
      notice_id: noticeId,
      notice_snapshot: noticeSnapshot,
      initial_step: initialStep,
    }),

  // Phase 4-G P0: 단일 세션 조회 (새로고침 복원용, PRD §13.9)
  getSession: (sessionId) =>
    req('GET', `/api/analysis/sessions/${encodeURIComponent(sessionId)}`),

  // 사이드바 X 버튼 — soft delete (status='abandoned')
  deleteSession: (sessionId) =>
    req('DELETE', `/api/analysis/sessions/${encodeURIComponent(sessionId)}`),

  // Phase 4-G P0: 세션 목록 (active session reuse용, Notice:Session 1:N)
  // backend는 status 단일만 받음 → status 필터는 frontend에서 수행
  listSessions: ({ userId, noticeId, limit = 20 } = {}) => {
    const params = new URLSearchParams()
    if (userId) params.set('user_id', userId)
    if (noticeId != null) params.set('notice_id', noticeId)
    if (limit != null) params.set('limit', limit)
    const qs = params.toString()
    return req('GET', `/api/analysis/sessions${qs ? '?' + qs : ''}`)
  },

  // Phase 4-G-2: 공고문 분석 (notice_analyst)
  parseNotice: ({ sessionId, noticeText, requestId = '' }) =>
    req('POST', '/api/analysis/parse-notice', {
      notice_text: noticeText,
      session_id: sessionId,
      request_id: requestId,
    }),

  // Phase 4-G-3: 양식 분석 (form_parser)
  // 2026-05-18: parserMode 추가 — "single" (default) | "hybrid" (regex chapter + 병렬 호출)
  parseForm: ({ sessionId, formText, formName = '', requestId = '', parserMode = 'hybrid' }) =>
    req('POST', '/api/analysis/parse-form', {
      form_text: formText,
      form_name: formName,
      session_id: sessionId,
      request_id: requestId,
      parser_mode: parserMode,
    }),

  // 2026-05-18: FormSchema section CRUD
  patchFormSchemaSection: ({ sessionId, action, sectionId = null, payload = null, targetIndex = null, insertPosition = null, force = false }) =>
    req('PATCH', '/api/analysis/form-schema/section', {
      session_id: sessionId,
      action,
      section_id: sectionId,
      payload,
      target_index: targetIndex,
      insert_position: insertPosition,
      force,
    }),

  // form_prd/4.md + 5.md: FormSchema question 수정/추가/제외
  //   action: 'update' | 'add' | 'exclude'
  //   update:  { sessionId, action:'update', questionId, payload }
  //   add:     { sessionId, action:'add', sectionId, payload }       // payload.title 필수
  //   exclude: { sessionId, action:'exclude', questionId, excluded } // excluded:true→배열 추가, false→제거
  //   응답 shape: { session_id, action, saved, updated_schema }
  // 2026-05-18 확장: action 추가 — 'move' / 'delete' + insertPosition for 'add'
  //   move:   { sessionId, action:'move', questionId, targetSectionId, targetIndex? }
  //   delete: { sessionId, action:'delete', questionId }
  //   add:    { sessionId, action:'add', sectionId, payload, insertPosition? } — insertPosition: { before/after: questionId }
  patchFormSchemaQuestion: ({
    sessionId, action, questionId, sectionId, payload, excluded,
    insertPosition = null, targetSectionId = null, targetIndex = null,
  }) =>
    req('PATCH', '/api/analysis/form-schema/question', {
      session_id: sessionId,
      action,
      question_id: questionId,
      section_id: sectionId,
      payload,
      excluded,
      insert_position: insertPosition,
      target_section_id: targetSectionId,
      target_index: targetIndex,
    }),

  // Phase 4-G-3: 참고자료 evidence 추출 (evidence_extractor)
  extractEvidence: ({ sessionId, refText, sourceFile = '', sourcePage = 0, requestId = '' }) =>
    req('POST', '/api/analysis/extract-evidence', {
      ref_text: refText,
      source_file: sourceFile,
      source_page: sourcePage,
      session_id: sessionId,
      request_id: requestId,
    }),

  // Phase 4-G-3: 기업 자료 분석 (company_analyzer)
  analyzeCompany: ({ sessionId, companyFiles = [], noticeSchema = {}, requestId = '' }) =>
    req('POST', '/api/analysis/analyze-company', {
      company_files: companyFiles,
      notice_schema: noticeSchema,
      session_id: sessionId,
      request_id: requestId,
    }),

  // Phase 4-G-4: evidence ↔ form 매핑 (evidence_mapper)
  mapEvidence: ({ sessionId, formSchema, evidenceList = [], noticeSchema = {}, matchingThreshold = 0.70, requestId = '' }) =>
    req('POST', '/api/analysis/map-evidence', {
      form_schema: formSchema,
      evidence_list: evidenceList,
      notice_schema: noticeSchema,
      matching_threshold: matchingThreshold,
      session_id: sessionId,
      request_id: requestId,
    }),

  // Phase 4-G-4: 부족자료 검출 (missing_material)
  checkMissing: ({ sessionId, mappingResult, requestId = '' }) =>
    req('POST', '/api/analysis/check-missing', {
      mapping_result: mappingResult,
      session_id: sessionId,
      request_id: requestId,
    }),

  // Phase 4-G-4: 평가기준 ↔ 문항 매핑 (PRD §16.1)
  mapEvalCriteria: ({ sessionId, noticeSchema, formSchema, requestId = '' }) =>
    req('POST', '/api/analysis/map-eval-criteria', {
      notice_schema: noticeSchema,
      form_schema: formSchema,
      session_id: sessionId,
      request_id: requestId,
    }),

  // v0.2.1 V1+V3: 사용자 편집된 평가기준 매핑 list (PRD-13 §19)
  listEvalCriteriaMappings: (sessionId) =>
    req('GET', `/api/analysis/eval-criteria-mappings?session_id=${encodeURIComponent(sessionId)}`),

  // v0.2.1 V1+V3: 평가기준 매핑 upsert (PATCH, mapped_by="user" 자동)
  updateEvalCriteriaMapping: ({ criteriaId, payload }) =>
    req('PATCH', `/api/analysis/eval-criteria-mappings/${encodeURIComponent(criteriaId)}`, payload),

  // Phase 4-G-5: Step 2 분석 확정 (no LLM, PRD §16.6)
  confirmStep2: ({ sessionId, evalCriteriaMappingId = null, confirmedFormSchema = null, requestId = '' }) =>
    req('POST', '/api/analysis/confirm-step2', {
      session_id: sessionId,
      eval_criteria_mapping_id: evalCriteriaMappingId,
      confirmed_form_schema: confirmedFormSchema,
      request_id: requestId,
    }),

  // Phase 4-G-7a: 부족자료 보완 (PRD §13.6, §16.3)
  missingText: ({ sessionId, questionId, missingId = null, content, requestId = '' }) =>
    req('POST', '/api/analysis/missing/text', {
      session_id: sessionId,
      question_id: questionId,
      missing_id: missingId,
      content,
      request_id: requestId,
    }),

  missingUpload: ({ sessionId, questionId, missingId = null, fileName, fileSizeBytes = 0, requestId = '' }) =>
    req('POST', '/api/analysis/missing/upload', {
      session_id: sessionId,
      question_id: questionId,
      missing_id: missingId,
      file_name: fileName,
      file_size_bytes: fileSizeBytes,
      request_id: requestId,
    }),

  missingBulkUpload: ({ sessionId, files = [], targetQuestionId = null, requestId = '' }) =>
    req('POST', '/api/analysis/missing/bulk-upload', {
      session_id: sessionId,
      files,
      target_question_id: targetQuestionId,
      request_id: requestId,
    }),

  missingConfirm: ({ sessionId, supplementalId, action, newQuestionId = null, requestId = '' }) =>
    req('POST', '/api/analysis/missing/confirm', {
      session_id: sessionId,
      supplemental_id: supplementalId,
      action,
      new_question_id: newQuestionId,
      request_id: requestId,
    }),

  reanalyze: ({ sessionId, target, force = false, requestId = '' }) =>
    req('POST', '/api/analysis/reanalyze', {
      session_id: sessionId,
      target,
      force,
      request_id: requestId,
    }),

  // Phase 4-G-8: Step 5 DOCX export (no LLM 게이트, PRD §11.5 / PRD §16.6)
  exportDocx: ({ sessionId, includeTableData = true, requestId = '' }) =>
    req('POST', '/api/analysis/export-docx', {
      session_id: sessionId,
      include_table_data: includeTableData,
      request_id: requestId,
    }),

  // Phase 4-G-6: 문항별 초안 작성 (draft_writer)
  writeDraftItem: ({ sessionId, question, matchedEvidence = [], companySchema = {}, noticeSchema = {}, writingGuidelines = null, constraints = null, requestId = '' }) =>
    req('POST', '/api/analysis/write-draft-item', {
      session_id: sessionId,
      question,
      matched_evidence: matchedEvidence,
      company_schema: companySchema,
      notice_schema: noticeSchema,
      writing_guidelines: writingGuidelines,
      constraints,
      request_id: requestId,
    }),

  // 스트리밍 초안 작성 — SSE로 토큰 즉시 수신
  writeDraftItemStream: ({ sessionId, question, matchedEvidence = [], companySchema = {}, noticeSchema = {}, writingGuidelines = null, constraints = null }) =>
    fetch('/api/analysis/write-draft-item-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId, question, matched_evidence: matchedEvidence,
        company_schema: companySchema, notice_schema: noticeSchema,
        writing_guidelines: writingGuidelines, constraints,
      }),
    }),

  // Phase 4-G-6: 초안 재작성 (draft_rewriter)
  rewriteDraftItem: ({ sessionId, questionId, currentDraft, userMessage, evidenceList = [], requestId = '' }) =>
    req('POST', '/api/analysis/rewrite-draft-item', {
      session_id: sessionId,
      question_id: questionId,
      current_draft: currentDraft,
      user_message: userMessage,
      evidence_list: evidenceList,
      request_id: requestId,
    }),

  // Phase 4-G-6: DraftItem 승인 (no LLM)
  approveDraftItem: ({ sessionId, questionId, draftItemId = null, requestId = '' }) =>
    req('POST', '/api/analysis/approve-draft-item', {
      session_id: sessionId,
      question_id: questionId,
      draft_item_id: draftItemId,
      request_id: requestId,
    }),

  // Phase 4-G-6: 세션의 DraftItem 목록 조회
  getDraftItems: (sessionId) =>
    req('GET', `/api/analysis/draft-items/${encodeURIComponent(sessionId)}`),

  // ── Phase 4-H A1: Step 1 multipart 파일 영속화 ─────────────
  // storage: ApplicationSession JSON-piggyback (notice_schema_json / form_schema_json)
  // kind: 'notice' | 'form' (references는 A3 범위)
  uploadFromUrl: ({ sessionId, kind = 'notice', url, filename = '' }) =>
    req('POST', '/api/analysis/files/upload-from-url', { session_id: sessionId, kind, url, filename }),

  uploadFile: async ({ sessionId, kind, file }) => {
    const fd = new FormData()
    fd.append('session_id', sessionId)
    fd.append('kind', kind)
    fd.append('file', file)
    const res = await fetch('/api/analysis/files/upload', { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail ?? `HTTP ${res.status}`)
    }
    return res.json()
  },

  listFiles: ({ sessionId, kind } = {}) => {
    const params = new URLSearchParams({ session_id: sessionId })
    if (kind) params.set('kind', kind)
    return req('GET', `/api/analysis/files?${params.toString()}`)
  },

  deleteFile: ({ sessionId, fileId }) =>
    req('DELETE', `/api/analysis/files/${encodeURIComponent(fileId)}?session_id=${encodeURIComponent(sessionId)}`),

  // ── Phase 4-H A2: drafts_preservation_policy (PRD §13.9) ───
  setDraftsPolicy: ({ sessionId, draftsPolicy }) =>
    req('PATCH', `/api/analysis/sessions/${encodeURIComponent(sessionId)}/drafts-policy`,
        { drafts_policy: draftsPolicy }),

  // ─────────────────────────────────────────────────────────────────
  // v3.2 C-5: backend C/B 흐름 연결용 wrapper 8개
  // ─────────────────────────────────────────────────────────────────

  // C-1: selected_company_file_ids PATCH (기존 reference_file_ids는 미수정)
  patchSession: ({ sessionId, selectedCompanyFileIds = null }) => {
    const body = {}
    if (selectedCompanyFileIds !== null) {
      body.selected_company_file_ids = selectedCompanyFileIds
    }
    return req('PATCH', `/api/analysis/sessions/${encodeURIComponent(sessionId)}`, body)
  },

  // C-1.5: announcement_signals 정규화
  normalizeAnnouncementSignals: (sessionId) =>
    req('POST', `/api/analysis/sessions/${encodeURIComponent(sessionId)}/announcement-signals/normalize`, {}),

  // C-1.6: evaluation_rubric 확정
  resolveEvaluationRubric: (sessionId) =>
    req('POST', `/api/analysis/sessions/${encodeURIComponent(sessionId)}/evaluation-rubric/resolve`, {}),

  // B-2: Step 3 진입 게이트 + confirmed_schema 재조회
  getStep3Ready: (sessionId) =>
    req('GET', `/api/analysis/sessions/${encodeURIComponent(sessionId)}/step3-ready`),

  // B-3: draft_items skeleton 생성 (idempotent)
  initializeDraftItems: ({ sessionId, requestId = '' }) =>
    req('POST', `/api/analysis/sessions/${encodeURIComponent(sessionId)}/draft-items/initialize`, {
      request_id: requestId,
    }),

  // C-3: mapping pipeline 비동기 시작 (5단계)
  runStep2Mapping: ({ sessionId, requestId = '' }) =>
    req('POST', '/api/analysis/run-step2-mapping', {
      session_id: sessionId,
      request_id: requestId,
    }),

  // C-3: failed pipeline 재실행 (done step skip)
  retryStep2Mapping: ({ sessionId, requestId = '' }) =>
    req('POST', '/api/analysis/retry-step2-mapping', {
      session_id: sessionId,
      request_id: requestId,
    }),

  // C-4: mapping pipeline 결과 + readiness 조회
  getMappingStatus: (sessionId) =>
    req('GET', `/api/analysis/sessions/${encodeURIComponent(sessionId)}/mapping-status`),
}

// 자료실 API (m-2, 2026-05-25) — /api/library/*
export const libraryApi = {
  list: ({ category, sort = 'recent' } = {}) => {
    const params = new URLSearchParams()
    if (category && category !== '전체') params.set('category', category)
    params.set('sort', sort)
    return req('GET', `/api/library/files?${params.toString()}`)
  },
  get: (fileId) =>
    req('GET', `/api/library/files/${encodeURIComponent(fileId)}`),
  upload: async ({ file, category }) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('category', category)
    const res = await fetch(`${BASE}/api/library/files`, {
      method: 'POST',
      body: fd,
    })
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new Error(`업로드 실패 (HTTP ${res.status}) ${text}`)
    }
    return res.json()
  },
  remove: (fileId) =>
    req('DELETE', `/api/library/files/${encodeURIComponent(fileId)}`),
}

// ── v0.2 CompanyFile API (PRD §13.10 / §3.2) — Phase 4-H A3 ────────
// 기업프로필 자료 — 기업설정에서 영구 저장. Step 1 카드 4번에서 선택만.
export const companyApi = {
  listFiles: ({ companyProfileId = 'anonymous', fileType, status = 'active' } = {}) => {
    const params = new URLSearchParams({ company_profile_id: companyProfileId })
    if (fileType) params.set('file_type', fileType)
    if (status) params.set('status', status)
    return req('GET', `/api/company/files?${params.toString()}`)
  },

  getFile: (fileId) => req('GET', `/api/company/files/${encodeURIComponent(fileId)}`),

  uploadFile: async ({ companyProfileId = 'anonymous', fileType = '기타', file }) => {
    const fd = new FormData()
    fd.append('company_profile_id', companyProfileId)
    fd.append('file_type', fileType)
    fd.append('file', file)
    const res = await fetch('/api/company/files', { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail ?? `HTTP ${res.status}`)
    }
    return res.json()
  },

  deleteFile: (fileId) =>
    req('DELETE', `/api/company/files/${encodeURIComponent(fileId)}`),
}

// ── /api/chat/* (PRD §16.5) ──────────────────────────────
export const chatApi = {
  // Phase 4-G-6: 작성 보조 대화 (chat_review)
  draftAssist: ({ sessionId, questionId, message, draftContent = '', noticeTitle = '', history = [], requestId = '' }) =>
    req('POST', '/api/chat/draft-assist', {
      session_id: sessionId,
      question_id: questionId,
      message,
      draft_content: draftContent,
      notice_title: noticeTitle,
      history,
      request_id: requestId,
    }),
}
